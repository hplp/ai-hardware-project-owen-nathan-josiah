# -*- coding: utf-8 -*-
"""Copy of AI_Hardware_Project.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1ABoCb0WDNPdZDAMXZSiHjbVFM2K8Av7q
"""

import torch
print("GPU available =", torch.cuda.is_available())

!pip install thop segmentation-models-pytorch transformers
!pip install pretrainedmodels
!pip install --upgrade certifi
import math
import numpy as np
import torch
import torch.nn as nn
import gc
import torchvision
from torchvision import datasets, transforms
from PIL import Image
import segmentation_models_pytorch as smp
import thop
from transformers import ViTFeatureExtractor, ViTForImageClassification
import matplotlib.pyplot as plt
from tqdm import tqdm
import time
import timm
import pretrainedmodels

# we won't be doing any training here, so let's disable autograd
torch.set_grad_enabled(False)

# convert to RGB class - some of the Caltech101 images are grayscale and do not match the tensor shapes
class ConvertToRGB:
    def __call__(self, image):
        # If grayscale image, convert to RGB
        if image.mode == "L":
            image = Image.merge("RGB", (image, image, image))
        return image

# Define transformations
transform = transforms.Compose([
    ConvertToRGB(), # first convert to RGB
    transforms.Resize((224, 224)),  # Most pretrained models expect 224x224 inputs
    transforms.ToTensor(),
    # this normalization is shared among all of the torch-hub models we will be using
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Download classification models
#mobile net v1 cant be downloaded through torchvision or timm, git clone didnt work either
mobilenet_v2_model = torchvision.models.mobilenet_v2(pretrained=True)
inception_v4_model = timm.create_model('inception_v4', pretrained=True)
vit_large_model = ViTForImageClassification.from_pretrained('google/vit-large-patch16-224')

# Move models to GPU

mobilenet_v2_model = mobilenet_v2_model.to("cuda").eval()
inception_v4_model = inception_v4_model.to("cuda").eval()
vit_large_model = vit_large_model.to("cuda").eval()

# denormalization function
def denormalize(tensor, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]):
    """ Denormalizes an image tensor that was previously normalized. """
    for t, m, s in zip(tensor, mean, std):
        t.mul_(s).add_(m)
    return tensor

# image show function
def imshow(tensor):
    """ Display a tensor as an image. """
    tensor = tensor.permute(1, 2, 0)  # Change from C,H,W to H,W,C
    tensor = denormalize(tensor)  # Denormalize if the tensor was normalized
    tensor = tensor*0.24 + 0.5 # fix the image range, it still wasn't between 0 and 1
    plt.imshow(tensor.clamp(0,1).cpu().numpy()) # plot the image
    plt.axis('off')

caltech101_dataset = datasets.Caltech101(root="./data", download=True, transform=transform)

# set a manual seed for determinism
from torch.utils.data import DataLoader
torch.manual_seed(42)
dataloader = DataLoader(caltech101_dataset, batch_size=16, shuffle=True)

# Dictionary to store results
accuracies = {"MobileNetV2": 0, "InceptionV4": 0}
total_samples = 0

num_batches = len(dataloader)

t_start = time.time()

with torch.no_grad():
  for i, (inputs, _)in tqdm(enumerate(dataloader), desc="Processing batches", total=num_batches):

        if i > 10:
          break

        # move the inputs to the GPU
        inputs = inputs.to("cuda")

        output = vit_large_model(inputs*0.5)
        baseline_preds = output.logits.argmax(-1)

        # MobileNetV2 predictions
        # logits_mobilenetv2 = mobilenet_v2_model(inputs)
        # top5_preds_mobilenetv2 = logits_mobilenetv2.topk(5, dim=1).indices
        # matches_mobilenetv2 = (baseline_preds.unsqueeze(1) == top5_preds_mobilenetv2).any(dim=1).float().sum().item()

        # # InceptionV4 predictions
        logits_inceptionv4 = inception_v4_model(inputs)
        top5_preds_inceptionv4 = logits_inceptionv4.topk(5, dim=1).indices
        matches_inceptionv4 = (baseline_preds.unsqueeze(1) == top5_preds_inceptionv4).any(dim=1).float().sum().item()

        # Update accuracies
        # accuracies["MobileNetV2"] += matches_mobilenetv2
        accuracies["InceptionV4"] += matches_inceptionv4
        total_samples += inputs.size(0)

print()
print(f"took {time.time()-t_start}s")

# Finalize the accuracies
accuracies["MobileNetV2"] /= total_samples
accuracies["InceptionV4"] /= total_samples

