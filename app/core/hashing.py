"""
=== 通用模块（可复用到其他项目）===

说明：
- bcrypt 哈希封装，跟业务无任何关系
- 复制到任何需要密码哈希的项目直接能用

使用时：
    hash_password("明文")       → 得到哈希值（注册时用）
    verify_password("明文", "哈希")  → True/False（登录时验证）
"""
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
