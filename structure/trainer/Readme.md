## output

```
(k8s-venv) root@LAPTOP-R4SU0DN5:~/K8-Project/src# python -m trainer.train
🚀 Training on: cuda
📊 Dataset: 104 train, 26 test.
Epoch: 010, Loss: 0.2129, Train Acc: 0.7692, Test Acc: 0.6538
Epoch: 020, Loss: 0.2155, Train Acc: 0.2788, Test Acc: 0.4231
Epoch: 030, Loss: 0.1687, Train Acc: 0.2788, Test Acc: 0.4231
Epoch: 040, Loss: 0.2233, Train Acc: 0.8846, Test Acc: 0.8462
Epoch: 050, Loss: 0.1869, Train Acc: 0.9423, Test Acc: 0.8846
Epoch: 060, Loss: 0.1725, Train Acc: 0.6635, Test Acc: 0.5000
Epoch: 070, Loss: 0.2697, Train Acc: 0.9327, Test Acc: 0.8846
Epoch: 080, Loss: 0.2070, Train Acc: 0.9519, Test Acc: 0.8846
Epoch: 090, Loss: 0.1414, Train Acc: 0.9615, Test Acc: 0.9615
Epoch: 100, Loss: 0.1851, Train Acc: 0.8846, Test Acc: 0.8462

--- Final Validation Classification Report ---
              precision    recall  f1-score   support

     Healthy       0.79      1.00      0.88        15
     Failure       1.00      0.64      0.78        11

    accuracy                           0.85        26
   macro avg       0.89      0.82      0.83        26
weighted avg       0.88      0.85      0.84        26
```
