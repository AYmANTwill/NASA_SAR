"""U-Net (ResNet-34 encoder, smp 0.6) with Dropout2d before the segmentation head (for MC dropout)."""
from __future__ import annotations

import segmentation_models_pytorch as smp
import torch
import torch.nn as nn


class WaterUNet(nn.Module):
    def __init__(self, dropout: float = 0.2, encoder_weights: str | None = "imagenet"):
        super().__init__()
        self.net = smp.Unet("resnet34", encoder_weights=encoder_weights, in_channels=2, classes=1)
        self.dropout = nn.Dropout2d(dropout)

    def forward(self, x):
        dec = self.net.decoder(self.net.encoder(x))
        return self.net.segmentation_head(self.dropout(dec))


def load_model(path, device="cpu") -> WaterUNet:
    ck = torch.load(path, map_location=device, weights_only=False)
    m = WaterUNet(dropout=ck.get("dropout", 0.2), encoder_weights=None)
    m.load_state_dict(ck["state_dict"])
    return m.to(device).eval()


def enable_mc_dropout(m: nn.Module) -> None:
    """Eval mode everywhere (BN frozen) except dropout layers."""
    m.eval()
    for mod in m.modules():
        if isinstance(mod, (nn.Dropout, nn.Dropout2d)):
            mod.train()
