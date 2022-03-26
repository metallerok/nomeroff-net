"""
python3 ./convert_ocr_to_onnx.py
"""
import sys
import os
import time
import pathlib
import torch
import argparse
import numpy as np
import onnxruntime

sys.path.append(os.path.join(os.path.abspath(os.getcwd()), "../../../../"))
from nomeroff_net.pipes.number_plate_text_readers.text_detector import TextDetector


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("-f", "--filepath",
                    default=os.path.join(os.path.abspath(os.getcwd()),
                                         "../../../../data/model_repository/base-ocr/1/model.onnx"),
                    required=False,
                    type=str,
                    help="Result onnx model filepath")
    ap.add_argument("-b", "--batch_size",
                    default=1,
                    required=False,
                    type=int,
                    help="Batch Size")
    ap.add_argument("-n", "--number_tests",
                    default=1,
                    required=False,
                    type=int,
                    help="Number of retry tine tests")
    args = vars(ap.parse_args())
    return args


def main():
    args = parse_args()
    filepath = args["filepath"]
    batch_size = args["batch_size"]
    n = args["number_tests"]

    # get models
    # Initialize text detector.
    text_detector = TextDetector()

    # get device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] device", device)

    # get model and model inputs
    model = text_detector.resnet18.resnet
    print(model)
    model = model.to(device)
    x = torch.rand((batch_size, 256, 4, 19), requires_grad=True)
    x = x.to(device)

    # make dirs
    p = pathlib.Path(os.path.dirname(filepath))
    p.mkdir(parents=True, exist_ok=True)

    # Export the model
    model.to_onnx(filepath, x,
                  export_params=True,  # store the trained parameter weights inside the model file
                  opset_version=10,  # the ONNX version to export the model to
                  do_constant_folding=True,  # whether to execute constant folding for optimization
                  input_names=[f'inp'],  # the model's input names
                  output_names=[f'out'],  # the model's output names
                  dynamic_axes={
                      f'inp': {0: 'batch_size'},  # variable length axes
                      f'out': {1: 'batch_size'},
                  })

    # Test torch model
    _ = model(x)
    start_time = time.time()
    for _ in range(n):
        _ = model(x)
    print(f"[INFO] torch time {(time.time() - start_time)/n * 1000}ms torch")

    # Load onnx model
    ort_session = onnxruntime.InferenceSession(filepath, providers=['TensorrtExecutionProvider',
                                                                     'CUDAExecutionProvider',
                                                                     'CPUExecutionProvider'])
    input_name = ort_session.get_inputs()[0].name
    ort_inputs = {
        input_name: np.random.randn(
            batch_size, 256, 4, 19
        ).astype(np.float32)
    }

    # run onnx model
    print(f"[INFO] available_providers", onnxruntime.get_available_providers())
    _ = ort_session.run(None, ort_inputs)
    start_time = time.time()
    for _ in range(n):
        _ = ort_session.run(None, ort_inputs)
    print(f"[INFO] onnx time {(time.time() - start_time)/n * 1000}ms tensorrt")


if __name__ == "__main__":
    main()

