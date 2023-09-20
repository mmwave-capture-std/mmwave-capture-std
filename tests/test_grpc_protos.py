import pytest

import grpc

import os
import sys

sys.path.insert(0, os.getcwd())

import cascadedradar_pb2
import cascadedradar_pb2_grpc


@pytest.fixture
def ch():
    return grpc.insecure_channel("localhost:50051")


@pytest.fixture
def stub(ch):
    return cascadedradar_pb2_grpc.CascadedRadarStub(ch)


def test_grpc_protos(ch, stub):
    req = cascadedradar_pb2.ConnectTdaRequest(ip="192.168.33.180", port=5001)
    res = stub.ConnectTda(req)
    assert res.ret_val == 0
