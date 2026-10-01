# Adapted from the official Laya Kaggle notebook
# (NandhaKishorM/laya notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb, Apache-2.0).
# Changes: calibration uses our own held-out `calib` split instead of carving it out of train,
# configurable max_len/head_max_len (Turkish options need a 384-token head budget), works with
# 1 or 2 GPUs, and records training metadata in rl_agent_config.json.
#
#   torchrun --standalone --nproc_per_node=<gpus> train_ddp.py MODEL_DIR OUTPUT_DIR TRAIN_PT CALIB_PT \
#       [--epochs 4] [--max-len 512] [--head-max-len 384] [--model-name laya-butik-tr]
import argparse
import json
import os
import random
import time

import torch
import torch.distributed as dist
from safetensors.torch import load_file, save_file
from torch.nn.parallel import DistributedDataParallel as DDP
from transformers import AutoTokenizer

from laya.common import build_model, proper_reward


def collate_train_batch(items, pad_id):
    n, L = len(items), max(len(it["ids"]) for it in items)
    kmax = max(len(it["markers"]) for it in items)
    ids = torch.full((n, L), pad_id, dtype=torch.long)
    att = torch.zeros((n, L), dtype=torch.long)
    mpos = torch.zeros((n, kmax), dtype=torch.long)
    mmask = torch.zeros((n, kmax), dtype=torch.bool)
    target = torch.zeros((n, kmax), dtype=torch.float32)
    for i, it in enumerate(items):
        ids[i, : len(it["ids"])] = torch.tensor(it["ids"])
        att[i, : len(it["ids"])] = 1
        k = len(it["markers"])
        mpos[i, :k] = torch.tensor(it["markers"])
        mmask[i, :k] = True
        target[i, : len(it["target"])] = torch.tensor(it["target"], dtype=torch.float32)
    return {
        "input_ids": ids,
        "attention_mask": att,
        "marker_pos": mpos,
        "marker_mask": mmask,
        "target": target,
        "qtype": torch.tensor([it["qtype"] for it in items]),
        "label": torch.tensor([it["label"] for it in items]),
    }


def fit_one_temp(sel):
    if len(sel) < 10:
        return 1.0
    kmax = max(len(z) for z, _ in sel)
    Z = torch.full((len(sel), kmax), -1e4)
    T = torch.zeros((len(sel), kmax))
    for i, (z, t) in enumerate(sel):
        Z[i, : len(z)] = torch.tensor(z)
        T[i, : len(t)] = torch.tensor(t, dtype=torch.float32)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=100)

    def closure():
        opt.zero_grad()
        loss = -(T * torch.log_softmax(Z / log_t.exp(), -1)).sum(-1).mean()
        loss.backward()
        return loss

    opt.step(closure)
    return float(torch.clamp(log_t.exp(), 0.1, 10.0).item())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir")
    ap.add_argument("output_dir")
    ap.add_argument("train_pt")
    ap.add_argument("calib_pt")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=512)
    ap.add_argument("--head-max-len", type=int, default=384)
    ap.add_argument("--model-name", default="laya-butik-tr")
    ap.add_argument("--max-steps", type=int, default=None, help="smoke test: stop after N micro-batches")
    args = ap.parse_args()

    # CUDA on Kaggle; without it (local smoke test) fall back to gloo on CPU without mixed precision
    cuda = torch.cuda.is_available()
    dist.init_process_group("nccl" if cuda else "gloo")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    if cuda:
        torch.cuda.set_device(local_rank)
    device = torch.device("cuda", local_rank) if cuda else torch.device("cpu")

    with open(os.path.join(args.model_dir, "rl_agent_config.json")) as f:
        cfg = json.load(f)
    cfg["gradient_checkpointing"] = True
    cfg["max_tokens_per_batch"] = 4096
    cfg["max_len"] = args.max_len
    cfg["head_max_len"] = args.head_max_len

    tok = AutoTokenizer.from_pretrained(os.path.join(args.model_dir, "tokenizer"))
    model = build_model(cfg, encoder_dir=os.path.join(args.model_dir, "encoder"))
    model.load_state_dict(load_file(os.path.join(args.model_dir, "model.safetensors")), strict=True)
    model.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.head_checkpointing = True
    model.to(device)
    model.train()
    ddp_model = DDP(model, device_ids=[local_rank] if cuda else None, find_unused_parameters=True)

    train_items = torch.load(args.train_pt, weights_only=False)
    calib_items = torch.load(args.calib_pt, weights_only=False)
    if args.max_steps:
        calib_items = calib_items[:32]
    my_items = train_items[rank::world_size]

    EPOCHS = args.epochs
    MICRO_BATCH = 8
    GRAD_ACCUM = max(1, 8 // world_size)  # effective batch 64 sequences on 1 or 2 GPUs
    GROUP_SIZE = 4
    LR_ENCODER = 2.5e-5
    LR_HEAD = 1.0e-4
    SIGMA_START = 0.4
    SIGMA_END = 0.1

    enc_params = [p for n, p in ddp_model.named_parameters() if "encoder." in n]
    head_params = [p for n, p in ddp_model.named_parameters() if "encoder." not in n]
    optimizer = torch.optim.AdamW(
        [{"params": enc_params, "lr": LR_ENCODER}, {"params": head_params, "lr": LR_HEAD}], weight_decay=0.01
    )
    total_updates = (len(my_items) // (MICRO_BATCH * GRAD_ACCUM)) * EPOCHS
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, total_updates), eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=cuda)

    if rank == 0:
        print(f"Training on {world_size} GPU(s): {len(train_items)} train items, {len(calib_items)} calib items, "
              f"{len(my_items)} per rank, {EPOCHS} epochs, ~{total_updates} updates")
    t0 = time.time()

    for epoch in range(EPOCHS):
        random.seed(42 + epoch + rank)
        random.shuffle(my_items)
        epoch_loss, n_batches, accum_step = 0.0, 0, 0
        optimizer.zero_grad(set_to_none=True)
        progress = epoch / max(1, EPOCHS - 1)
        sigma = SIGMA_START + (SIGMA_END - SIGMA_START) * progress

        for b_idx in range(0, len(my_items), MICRO_BATCH):
            chunk = my_items[b_idx : b_idx + MICRO_BATCH]
            if not chunk:
                continue
            batch = collate_train_batch(chunk, tok.pad_token_id)
            with torch.autocast(device.type, dtype=torch.float16, enabled=cuda):
                logits, act = ddp_model(
                    batch["input_ids"].to(device),
                    batch["attention_mask"].to(device),
                    batch["marker_pos"].to(device),
                    batch["marker_mask"].to(device),
                    batch["qtype"].to(device),
                )
            logits = logits.float()
            mask = batch["marker_mask"].to(device)
            k = mask.sum(-1, keepdim=True).float()
            target = batch["target"].to(device)

            # Sample G noisy logit distributions with zero-mean projection
            eps = torch.randn((GROUP_SIZE,) + logits.shape, device=device) * sigma * mask
            eps = (eps - eps.sum(-1, keepdim=True) / k) * mask
            z = logits.detach().unsqueeze(0) + eps
            q = torch.softmax(z.masked_fill(~mask, -1e4), -1)

            # Proper scoring reward
            with torch.no_grad():
                r = proper_reward(q, target.unsqueeze(0), batch["qtype"].to(device), mask, w_sph=0.75, w_rps=1.0)
                adv = r - r.mean(0, keepdim=True)
                adv = adv / (adv.std() + 1e-6)

            # Policy gradient + soft cross-entropy guidance
            logp = -(((z - logits.unsqueeze(0)) ** 2) * mask).sum(-1) / (2 * sigma**2)
            loss_rl = -(adv * logp).mean()
            loss_ce = -(target * torch.log_softmax(logits.masked_fill(~mask, -1e4), -1)).sum(-1).mean()
            loss = (loss_rl + 1.0 * loss_ce) / GRAD_ACCUM + 0.0 * act.sum()

            scaler.scale(loss).backward()
            accum_step += 1
            if accum_step % GRAD_ACCUM == 0 or (b_idx + MICRO_BATCH) >= len(my_items):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(ddp_model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)

            epoch_loss += loss.item() * GRAD_ACCUM
            n_batches += 1
            if args.max_steps and n_batches >= args.max_steps:
                if rank == 0:
                    print(f"  smoke step {n_batches}: loss {loss.item() * GRAD_ACCUM:.4f} reward {r.mean().item():.3f}")
                break
            if rank == 0 and n_batches % 50 == 0:
                print(f"  Epoch {epoch + 1}/{EPOCHS} | Step {n_batches} | Loss {loss.item() * GRAD_ACCUM:.4f} | "
                      f"Reward {r.mean().item():.3f} | LR {scheduler.get_last_lr()[0]:.2e}", flush=True)

        if rank == 0:
            print(f"=== Epoch {epoch + 1}/{EPOCHS} done at {time.time() - t0:.0f}s | "
                  f"avg loss {epoch_loss / max(1, n_batches):.4f} ===", flush=True)
        dist.barrier()

        # Rolling checkpoint so a Kaggle timeout does not lose finished epochs
        if rank == 0:
            ckpt_dir = os.path.join(args.output_dir, "checkpoint_latest")
            os.makedirs(ckpt_dir, exist_ok=True)
            save_file({k: v.half().contiguous().cpu() for k, v in model.state_dict().items()},
                      os.path.join(ckpt_dir, "model.safetensors"))
            with open(os.path.join(ckpt_dir, "checkpoint_meta.json"), "w") as f:
                json.dump({"epoch": epoch + 1, "total_epochs": EPOCHS,
                           "avg_loss": epoch_loss / max(1, n_batches)}, f, indent=2)

    dist.barrier()

    if rank == 0:
        print("\nFitting calibration temperatures on the held-out calib split...")
        del optimizer, scaler, scheduler
        if cuda:
            torch.cuda.empty_cache()
        model.eval()
        calib_preds = []
        with torch.no_grad():
            for c_idx in range(0, len(calib_items), 16):
                c_chunk = calib_items[c_idx : c_idx + 16]
                cb = collate_train_batch(c_chunk, tok.pad_token_id)
                with torch.autocast(device.type, dtype=torch.float16, enabled=cuda):
                    l_sub, _ = model(
                        cb["input_ids"].to(device),
                        cb["attention_mask"].to(device),
                        cb["marker_pos"].to(device),
                        cb["marker_mask"].to(device),
                        cb["qtype"].to(device),
                    )
                l_np = l_sub.float().cpu().numpy()
                for r_i, it in enumerate(c_chunk):
                    calib_preds.append((it["qtype"], l_np[r_i, : len(it["markers"])], it["target"]))

        fitted = [1.2, 1.2, 1.2]  # QTYPES order: choice, score, noul
        try:
            for qt in range(3):
                sel = [(z, t) for q_type, z, t in calib_preds if q_type == qt]
                if sel:
                    fitted[qt] = fit_one_temp(sel)
            print("Fitted temperatures (choice, score, noul):", [round(t, 3) for t in fitted])
        except Exception as e:  # noqa: BLE001
            print("Temperature fitting fallback:", e)

        os.makedirs(args.output_dir, exist_ok=True)
        save_file({k: v.half().contiguous().cpu() for k, v in model.state_dict().items()},
                  os.path.join(args.output_dir, "model.safetensors"))
        model.encoder.config.save_pretrained(os.path.join(args.output_dir, "encoder"))
        tok.save_pretrained(os.path.join(args.output_dir, "tokenizer"))
        cfg["fine_tuned"] = True
        cfg["model_name"] = args.model_name
        cfg["temperature"] = fitted
        cfg.pop("temperature_by_options", None)
        cfg["training"] = {"base": "convaiinnovations/laya-multilingual", "epochs": EPOCHS,
                           "train_items": len(train_items), "calib_items": len(calib_items),
                           "world_size": world_size, "minutes": round((time.time() - t0) / 60, 1)}
        with open(os.path.join(args.output_dir, "rl_agent_config.json"), "w") as f:
            json.dump(cfg, f, indent=2)
        print(f"Saved fine-tuned model to {args.output_dir}")

    dist.destroy_process_group()


if __name__ == "__main__":
    main()
