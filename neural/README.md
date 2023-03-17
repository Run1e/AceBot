# Game script prediction model architecture

To install PyTorch compiled for CUDA, see:
https://pytorch.org/

```
TextCNN(
  (embedding): Embedding(6442, 100, padding_idx=0)
  (convs): ModuleList(
    (0): Conv2d(1, 64, kernel_size=(2, 100), stride=(1, 1))
    (1): Conv2d(1, 64, kernel_size=(3, 100), stride=(1, 1))
  )
  (dropout): Dropout(p=0.5, inplace=False)
  (fc): Linear(in_features=128, out_features=1, bias=True)
  (sigmoid): Sigmoid()
)
Trainable params: 676457
```
