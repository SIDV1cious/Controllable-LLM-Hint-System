import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# 加载配置
load_dotenv()

# 构建连接地址
db_url = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
)

try:
    engine = create_engine(db_url)
    # 检查数据库里的表
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"🎉 成功！Python 已连上数据库")
    print(f"当前负责人学号：{os.getenv('MY_ID')}")
    print(f"仓库中的表：{tables}")
except Exception as e:
    print(f"❌ 哎呀，连接断了：{e}")
