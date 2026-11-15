"""U-Net (ResNet-34 encoder, smp 0.6) with Dropout2d before the segmentation head (for MC dropout)."""
from __future__ import annotations

import segmentation_models_pytorch as smp
import torch
import torch.nn as nn


class WaterUNet(nn.Module):
    def __init__(self, dropout: float = 0.2, encoder_weights: str | None = "imagenet", in_channels: int = 2):
        super().__init__()
        self.in_channels = in_channels  # 2 = HH/HV (VV/VH slots); 3 = + incidence angle (v3)
        self.net = smp.Unet("resnet34", encoder_weights=encoder_weights, in_channels=in_channels, classes=1)
        self.dropout = nn.Dropout2d(dropout)

    def forward(self, x):
        dec = self.net.decoder(self.net.encoder(x))
        return self.net.segmentation_head(self.dropout(dec))


def load_model(path, device="cpu") -> WaterUNet:
    ck = torch.load(path, map_location=device, weights_only=False)
    m = WaterUNet(dropout=ck.get("dropout", 0.2), encoder_weights=None, in_channels=ck.get("in_channels", 2))
    m.load_state_dict(ck["state_dict"])
    return m.to(device).eval()


def enable_mc_dropout(m: nn.Module) -> None:
    """Eval mode everywhere (BN frozen) except dropout layers."""
    m.eval()
    for mod in m.modules():
        if isinstance(mod, (nn.Dropout, nn.Dropout2d)):
            mod.train()


def widen_input(m: WaterUNet, n_new: int = 1) -> WaterUNet:
    """Copy of a 2-channel model with n_new extra input channels whose first-layer weights are zero, so the widened
    model starts with exactly the same predictions (v3: incidence angle)."""
    import copy

    w = copy.deepcopy(m)
    conv = w.net.encoder.conv1
    new = nn.Conv2d(conv.in_channels + n_new, conv.out_channels, conv.kernel_size, conv.stride, conv.padding,
                    bias=conv.bias is not None).to(conv.weight.device)
    with torch.no_grad():
        new.weight.zero_()
        new.weight[:, :conv.in_channels] = conv.weight
        if conv.bias is not None:
            new.bias.copy_(conv.bias)
    w.net.encoder.conv1 = new
    w.in_channels = conv.in_channels + n_new
    return w
