import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

x = torch.rand(10000, 10000, device=device)
print("Tensor created on:", x.device)

