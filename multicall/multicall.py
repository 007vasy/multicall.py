from typing import List

from multicall import Call
from multicall.constants import (
    MULTICALL2_ADDRESSES, 
    MULTICALL2_BYTECODE,
    MULTICALL_ADDRESSES, 
    w3
)
from multicall.signature import Signature
import json
from pathlib import Path

def load_abi(rel_file_path):

    file_content = {}

    file_dir = Path(__file__).parent

    with open(file_dir/rel_file_path) as f:
        file_content = json.load(f)

    return file_content

def get_multicall_map(chain_id):
    return MULTICALL_ADDRESSES if chain_id in MULTICALL_ADDRESSES else MULTICALL2_ADDRESSES

class Multicall:
    def __init__(self, calls: List[Call], _w3=None, block_id=None, require_success: bool=True):
        self.calls = calls
        self.block_id = block_id
        self.require_success = require_success

        if _w3 is None:
            self.w3 = w3
        else:
            self.w3 = _w3
        
        self.abi_rel_path = "mc_contract_abi_0xeefba1e63905ef1d7acba5a8513c70307c1ce441.json"

    def _load_abi(self):
        return load_abi(self.abi_rel_path)

    def multicall(self,args):
        contract = self.w3.eth.contract(address=self.multicall_contract_address, abi=self._load_abi())
 
        return contract.functions.aggregate([{"target":call.target, "callData":call.data} for call in self.calls]).call(
            block_identifier=self.block_id,
            state_override_code=MULTICALL2_BYTECODE)


    def __call__(self):
        
        if self.require_success is True:
            multicall_map = get_multicall_map(self.w3.eth.chain_id)
            self.multicall_sig = 'aggregate((address,bytes)[])(uint256,bytes[])'
        else:
            multicall_map = MULTICALL2_ADDRESSES
            self.multicall_sig = 'tryBlockAndAggregate(bool,(address,bytes)[])(uint256,uint256,(bool,bytes)[])'

        self.multicall_contract_address = multicall_map[self.w3.eth.chain_id]

        # aggregate = Call(
        #     self.multicall_contract_address,
        #     self.multicall_sig,
        #     returns=None,
        #     _w3=self.w3,
        #     block_id=self.block_id,
        #     state_override_code=MULTICALL2_BYTECODE
        # )

        if self.require_success is True:
            args = [[[call.target, call.data] for call in self.calls]]
            block_id, outputs = self.multicall(args)
            outputs = ((None, output) for output in outputs)
        else:
            args = [self.require_success, [[call.target, call.data] for call in self.calls]]
            block_id, _, outputs = self.multicall(args)
        
        self.resp_block_id = block_id
        print(f"Last block is > {self.resp_block_id} < on chain_id: > {self.w3.eth.chain_id} <")

        result = {}
        for call, (success, output) in zip(self.calls, outputs):
            result.update(call.decode_output(output, success))

        return result
