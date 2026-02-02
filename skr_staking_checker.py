#!/usr/bin/env python3
"""
SKR 質押查詢工具
查詢 Solana 錢包地址的 SKR 代幣質押量

使用方法:
python skr_staking_checker.py <錢包地址>

需要安裝: pip install solana solders --break-system-packages
"""

import sys
import json
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solana.rpc.types import TokenAccountOpts
from solana.rpc.types import MemcmpOpts
# Try importing TokenAccountsFilterMint, handle if it's in solders
try:
    from solders.rpc.requests import TokenAccountsFilterMint
except ImportError:
    # Backup: some versions might handle it differently or it's in a different submodule
    # For simplicity, we'll assume it will be available or we rely on the dict fallback
    pass

# SKR 代幣資訊
SKR_TOKEN_MINT = "SKRbvo6Gf7GondiT3BbTfuRDPqLWei4j2Qy2NPGZhW3"
SKR_STAKING_PROGRAM = "SKRskrmtL83pcL4YqLWt6iPefDqwXQWHSw9S9vz94BZ"

# Solana RPC 端點 (使用公共端點,建議替換為自己的 QuickNode 或其他 RPC)
SOLANA_RPC = "https://api.mainnet-beta.solana.com"


from solana.rpc.types import TokenAccountOpts

def get_token_accounts_by_owner(wallet_address: str, rpc_url: str = SOLANA_RPC):
    """
    取得錢包地址擁有的所有 SPL 代幣帳戶
    """
    try:
        client = Client(rpc_url)
        wallet_pubkey = Pubkey.from_string(wallet_address)
        mint_pubkey = Pubkey.from_string(SKR_TOKEN_MINT)
        
        # 查詢該錢包的所有 SKR 代幣帳戶
        # 改用 base64 編碼，避免 jsonParsed 在不同環境下的解析問題
        opts = TokenAccountOpts(mint=mint_pubkey, encoding='base64')
        
        response = client.get_token_accounts_by_owner(
            wallet_pubkey,
            opts
        )
        
        return response
    except Exception as e:
        print(f"錯誤: 無法連接到 Solana RPC 或查詢失敗: {e}")
        return None



def get_program_accounts(wallet_address: str, rpc_url: str = SOLANA_RPC):
    """
    查詢質押程式相關的帳戶
    """
    try:
        client = Client(rpc_url)
        staking_program_pubkey = Pubkey.from_string(SKR_STAKING_PROGRAM)
        
        # 查詢質押程式的所有帳戶
        response = client.get_program_accounts(staking_program_pubkey)
        
        return response
    except Exception as e:
        print(f"查詢質押帳戶時發生錯誤: {e}")
        return None


def format_token_amount(amount: int, decimals: int = 9) -> float:
    """
    將代幣的最小單位轉換為可讀格式
    SKR 使用 9 位小數
    """
    return amount / (10 ** decimals)


from solana.rpc.types import MemcmpOpts

def get_staked_balance(wallet_address: str, rpc_url: str = SOLANA_RPC) -> float:
    """
    查詢質押在合約中的餘額
    """
    try:
        client = Client(rpc_url)
        wallet_pubkey = Pubkey.from_string(wallet_address)
        STAKING_PROGRAM_ID = SKR_STAKING_PROGRAM

        # 1. Fetch User Stake Account
        # Using Memcmp filter for wallet address at offset 41 (confirmed by analysis)
        # Note: Previous analysis showed user wallet at offset 41 for Efxtw...
        filters = [
            MemcmpOpts(offset=41, bytes=str(wallet_pubkey))
        ]
        
        program_id = Pubkey.from_string(STAKING_PROGRAM_ID)
        response = client.get_program_accounts(program_id, filters=filters)
        
        if not response.value:
            # Fallback to offset 40 just in case (for other wallets)
            filters = [MemcmpOpts(offset=40, bytes=str(wallet_pubkey))]
            response = client.get_program_accounts(program_id, filters=filters)
            if not response.value:
                return 0.0

        user_account = response.value[0]
        u_data = user_account.account.data
        
        # User Shares at Offset 104
        if len(u_data) < 112:
            return 0.0
            
        user_shares = int.from_bytes(u_data[104:112], 'little')
        # print(f"User Shares: {user_shares}")

        # 2. Fetch Global State Account to get Exchange Rate
        # Global Account: 4aAEUKCcju9iAEAgdeaNz4RC7sCPv63q5g714nw4QY68
        GLOBAL_STATE_PUBKEY = Pubkey.from_string("4aAEUKCcju9iAEAgdeaNz4RC7sCPv63q5g714nw4QY68")
        
        g_resp = client.get_account_info(GLOBAL_STATE_PUBKEY)
        if not g_resp.value:
            print("無法讀取全域質押狀態")
            return 0.0
            
        g_data = g_resp.value.data
        
        # Total Staked Offset: 3616
        # Total Shares Offset: 1344
        if len(g_data) < 3624:
            print("全域狀態資料長度不足")
            return 0.0
            
        total_staked = int.from_bytes(g_data[3616:3624], 'little')
        total_shares = int.from_bytes(g_data[1344:1352], 'little')
        
        if total_shares == 0:
            return 0.0
            
        # Rate = Total Staked / Total Shares
        rate = total_staked / total_shares
        
        # User Balance = User Shares * Rate
        # Decimals = 9
        balance = (user_shares * rate) / 10**9
        
        return balance

    except Exception as e:
        print(f"查詢鏈上質押失敗: {e}")
        return 0.0


def check_skr_staking(wallet_address: str):
    """
    主函數:檢查指定錢包的 SKR 質押量
    """
    print(f"=" * 70)
    print(f"查詢錢包: {wallet_address}")
    print(f"SKR 代幣地址: {SKR_TOKEN_MINT}")
    print(f"質押程式: {SKR_STAKING_PROGRAM}")
    print(f"=" * 70)
    print()
    
    # 查詢錢包的 SKR 代幣餘額
    print("正在查詢錢包餘額...")
    token_accounts = get_token_accounts_by_owner(wallet_address)
    
    wallet_balance = 0
    if token_accounts and hasattr(token_accounts, 'value'):
        for account in token_accounts.value:
            if account.account and account.account.data:
                # 解析 SPL Token Account (Base64)
                data = account.account.data
                
                if isinstance(data, str):
                     # 如果是字符串 (Base64)，需要解碼
                     import base64
                     # 加回 padding
                     pad = len(data) % 4
                     if pad > 0:
                         data += "=" * (4 - pad)
                     try:
                        data_bytes = base64.b64decode(data)
                     except Exception as e:
                        print(f"  警告: 解析 base64 數據失敗: {e}")
                        continue
                else:
                     # 如果已經是 bytes (solders 自動解碼)，直接使用
                     data_bytes = bytes(data)
                
                if len(data_bytes) >= 72:
                    amount_raw = int.from_bytes(data_bytes[64:72], 'little')
                    ui_amount = amount_raw / (10 ** 6)
                    print(f"    - 帳戶 {account.pubkey}: {ui_amount:,.2f} SKR (原始: {amount_raw})")
                    wallet_balance += ui_amount
                
        print(f"  錢包內餘額總計: {wallet_balance:,.2f} SKR")
    else:
        print("  錢包內餘額: 0.00 SKR")
    print()
    
    # 查詢質押資訊
    print("正在查詢鏈上質押餘額...")
    staked_balance = get_staked_balance(wallet_address)
    
    print(f"  已質押餘額: {staked_balance:,.2f} SKR")
    print()
    
    total_assets = wallet_balance + staked_balance
    print(f"總資產 (錢包 + 質押): {total_assets:,.2f} SKR")
    print()
    
    print("=" * 70)
    print("查詢完成!")
    print("=" * 70)


def main():
    if len(sys.argv) < 2:
        print("使用方法: python skr_staking_checker.py <錢包地址>")
        print()
        print("範例:")
        print("python skr_staking_checker.py YourSolanaWalletAddressHere")
        sys.exit(1)
    
    wallet_address = sys.argv[1]
    
    # 驗證地址格式
    try:
        Pubkey.from_string(wallet_address)
    except Exception as e:
        print(f"錯誤: 無效的 Solana 錢包地址")
        print(f"請確認地址格式正確")
        sys.exit(1)
    
    check_skr_staking(wallet_address)


if __name__ == "__main__":
    main()
