from typing import Any, Tuple
import pytest
import os

from brownie import web3
from joblib import Parallel, delayed
from multicall import Call, Multicall
from multicall.multicall import batcher
from multicall.utils import await_awaitable

CHAI = '0x06AF07097C9Eeb7fD685c692751D5C66dB49c215'
DUMMY_CALL = Call(CHAI, 'totalSupply()(uint)', [['totalSupply',None]])
batcher.step = 10_000

def from_wei(val):
    return val / 1e18

def from_wei_require_success(success,val):
    assert success
    return val / 1e18

def from_ray(val):
    return val / 1e18

def from_ray_require_success(success,val):
    assert success
    return val / 1e27

def unpack_no_success(success: bool, output: Any) -> Tuple[bool,Any]:
    return (success, output)


def test_multicall():
    multi = Multicall([
        Call(CHAI, 'totalSupply()(uint256)', [['supply', from_wei]]),
        Call(CHAI, ['balanceOf(address)(uint256)', CHAI], [['balance', from_ray]]),
    ])
    result = multi()
    print(result)
    assert isinstance(result['supply'], float)
    assert isinstance(result['balance'], float)

def test_multicall_no_success():
    multi = Multicall(
        [
            Call(CHAI, 'transfer(address,uint256)(bool)', [['success', unpack_no_success]]), # lambda success, ret_flag: (success, ret_flag)
            Call(CHAI, ['balanceOf(address)(uint256)', CHAI], [['balance', unpack_no_success]]), # lambda success, value: (success, from_ray(value))
        ],
        require_success=False
    )
    result = multi()
    print(result)
    assert isinstance(result['success'], tuple)
    assert isinstance(result['balance'], tuple)

def test_multicall_async():
    multi = Multicall([
        Call(CHAI, 'totalSupply()(uint256)', [['supply', from_wei]]),
        Call(CHAI, ['balanceOf(address)(uint256)', CHAI], [['balance', from_ray]]),
    ])
    result = await_awaitable(multi.coroutine())
    print(result)
    assert isinstance(result['supply'], float)
    assert isinstance(result['balance'], float)

def test_multicall_no_success_async():
    multi = Multicall(
        [
            Call(CHAI, 'transfer(address,uint256)(bool)', [['success', unpack_no_success]]),
            Call(CHAI, ['balanceOf(address)(uint256)', CHAI], [['balance', unpack_no_success]]),
        ],
        require_success=False
    )
    result = await_awaitable(multi.coroutine())
    print(result)
    assert isinstance(result['success'], tuple)
    assert isinstance(result['balance'], tuple)

def test_batcher_batch_calls_even():
    batcher.step = 10_000
    calls = [DUMMY_CALL for i in range(30_000)]
    batches = batcher.batch_calls(calls,batcher.step)
    # NOTE batcher.step == 10_000, so with 30_000 calls you should have 3 batches
    assert len(batches) == 3
    for batch in batches:
        assert len(batch) <= batcher.step
    assert sum(len(batch) for batch in batches) == len(calls)

def test_batcher_batch_calls_odd():
    batcher.step = 10_000
    calls = [DUMMY_CALL for i in range(29_999)]
    batches = batcher.batch_calls(calls,batcher.step)
    # NOTE batcher.step == 10_000, so with 30_000 calls you should have 3 batches
    assert len(batches) == 3
    for batch in batches:
        assert len(batch) <= batcher.step
    assert sum(len(batch) for batch in batches) == len(calls)

def test_batcher_split_calls_even():
    calls = [DUMMY_CALL for i in range(30_000)]
    split = batcher.split_calls(calls,batcher.step)
    assert len(split) == 2
    assert sum(len(batch) for batch in split) == len(calls)
    assert len(split[0]) == 15_000
    assert len(split[1]) == 15_000

def test_batcher_split_calls_odd():
    calls = [DUMMY_CALL for i in range(29_999)]
    split = batcher.split_calls(calls,batcher.step)
    assert len(split) == 2
    assert sum(len(batch) for batch in split) == len(calls)
    assert len(split[0]) == 14_999
    assert len(split[1]) == 15_000

def test_batcher_step_down_and_retry():
    batcher.step = 100_000
    calls = [Call(CHAI, 'totalSupply()(uint)', [[f'totalSupply{i}',None]]) for i in range(100_000)]
    results = Multicall(calls)()
    assert batcher.step < 100_000
    assert len(results) == len(calls)

def test_multicall_threading():
    calls = [Call(CHAI, 'totalSupply()(uint)', [[f'totalSupply{i}',None]]) for i in range(50_000)]
    Parallel(4,'threading')(delayed(Multicall(batch))() for batch in batcher.batch_calls(calls, batcher.step))

@pytest.mark.skip(reason="upgraded web3")
def test_multicall_multiprocessing():
    # NOTE can't have middlewares for multiprocessing
    web3.provider.middlewares = tuple()
    web3.middleware_onion.clear()
    # TODO figure out why multiprocessing fails if you don't call request_func here
    web3.provider.request_func(web3, web3.middleware_onion)
    calls = [Call(CHAI, 'totalSupply()(uint)', [[f'totalSupply{i}',None]]) for i in range(50_000)]
    Parallel(4,'multiprocessing')(delayed(Multicall(batch, _w3=web3))() for batch in batcher.batch_calls(calls, batcher.step))

def test_multicall_complex_function_output():
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
    
    chain = "ethereum__mainnet"
    contract = "0x996913c8c08472f584ab8834e925b06d0eb1d813"
    staker_address = "0x06A2DE83a82B354Aa75887E5517655ccfA00a696"

    func_abi = {
        "inputs": [
            {
                "internalType": "address",
                "name": "staker",
                "type": "address"
            }
        ],
        "name": "calculateLatestStakerReward",
        "outputs": [
            {
                "components": [
                    {
                        "internalType": "uint112",
                        "name": "vestedBaseReward",
                        "type": "uint112"
                    },
                    {
                        "internalType": "uint112",
                        "name": "vestedDelegatedReward",
                        "type": "uint112"
                    },
                    {
                        "internalType": "uint112",
                        "name": "baseRewardPerToken",
                        "type": "uint112"
                    },
                    {
                        "internalType": "uint112",
                        "name": "operatorDelegatedRewardPerToken",
                        "type": "uint112"
                    },
                    {
                        "internalType": "enum IRewardVault.StakerType",
                        "name": "stakerType",
                        "type": "uint8"
                    },
                    {
                        "internalType": "uint112",
                        "name": "claimedBaseRewardsInPeriod",
                        "type": "uint112"
                    },
                    {
                        "internalType": "uint112",
                        "name": "unvestedBaseReward",
                        "type": "uint112"
                    }
                ],
                "internalType": "struct IRewardVault.StakerReward",
                "name": "",
                "type": "tuple"
            },
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
    function_name = func_abi["name"]
    mc_key = f'{chain}__{contract}__{function_name}__{staker_address}'
    mc_sig = 'calculateLatestStakerReward(address)((uint112,uint112,uint112,uint112,uint8,uint112,uint112),uint256)'
    _call = Call(contract, [mc_sig, staker_address], [[mc_key, unpack_no_success]])


        
    try:
        w3_url = os.environ.get("WEB3_PROVIDER_URI", None)

        w3 = Web3(Web3.HTTPProvider(w3_url,request_kwargs={'timeout': 60}))


        for block_number_attr_format in [
                'middleware_onion',
                'middleware_stack',
            ]:
            if hasattr(w3, block_number_attr_format):
                w3_middleware = getattr(w3, block_number_attr_format)

        w3_middleware.inject(geth_poa_middleware, layer=0)


        block_id = 18932295
        
        multi = Multicall([_call] ,_w3 = w3, 
            block_id=block_id, 
            require_success=False, gas_limit=999_999_999_999)

        resp = multi()

    except Exception as e:
        print(str(e))

    assert resp[mc_key] == (True, ((7898831300446505238,0,3020729914728570,0,1,0,0), 12254818851300487143))
