import mysql.connector
import time
from datetime import datetime
import hashlib
import os
import subprocess

# 配置部分
SQL_DIR = "./sql"
GIT_REPO_PATH = "."  # 假设脚本在仓库根目录下运行
GIT_REMOTE = "origin"  # Git远程仓库名称
GIT_BRANCH = "master"    # Git分支名称

# 确保sql目录存在
os.makedirs(SQL_DIR, exist_ok=True)

def git_push_changes(changes_info):
    """将变更推送到GitHub仓库"""
    try:
        # 切换到仓库目录
        os.chdir(GIT_REPO_PATH)
        
        # 检查是否有变更
        result = subprocess.run(["git", "status", "--porcelain"], 
                              capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            print("没有需要提交的变更")
            return False
        
        print("检测到文件变更，准备提交到GitHub...")
        
        # 添加所有变更
        subprocess.run(["git", "add", "."], check=True)
        
        # 提交变更
        subprocess.run(["git", "commit", "-m", changes_info], check=True)
        
        # 推送到远程仓库
        subprocess.run(["git", "push", GIT_REMOTE, GIT_BRANCH], check=True)
        
        print("成功推送到GitHub仓库")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git操作失败: {e.stderr}")
        return False
    except Exception as e:
        print(f"推送变更时出错: {str(e)}")
        return False

def get_table_hash(cursor, table_name):
    """获取表结构的哈希指纹和SQL语句"""
    cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
    result = cursor.fetchone()
    return hashlib.md5(result[1].encode()).hexdigest(), result[1]

def save_table_sql(table_name, sql_content):
    """保存表结构到SQL文件"""
    file_path = os.path.join(SQL_DIR, f"{table_name}.sql")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(sql_content)
    print(f"已保存表结构到: {file_path}")
    return True  # 返回True表示有变更

def delete_table_sql(table_name):
    """删除表的SQL文件"""
    file_path = os.path.join(SQL_DIR, f"{table_name}.sql")
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"已删除表结构文件: {file_path}")
        return True  # 返回True表示有变更
    return False

def monitor_schema_changes(interval=30):
    config = {
        'user': 'root',
        'password': 'root',
        'host': 'localhost',
        'port': 3306,
        'database': 'ccpc'
    }
    
    last_hashes = {}
    last_tables = set()
    first_run = True
    changes_detected = False  # 跟踪是否有变更需要提交
    changes_info = ''
    
    while True:
        try:
            conn = mysql.connector.connect(**config)
            cursor = conn.cursor()
            
            cursor.execute("SHOW TABLES")
            current_tables = {row[0] for row in cursor.fetchall()}
            
            if not first_run:
                # 检测新增的表
                new_tables = current_tables - last_tables
                for table in new_tables:
                    current_hash, create_sql = get_table_hash(cursor, table)
                    print(f"[{datetime.now()}] 检测到新表创建: `{table}`")
                    last_hashes[table] = current_hash
                    if save_table_sql(table, create_sql):
                        changes_detected = True
                        changes_info += f"创建新表：`{table}`\n"
                
                # 检测被删除的表
                removed_tables = last_tables - current_tables
                for table in removed_tables:
                    print(f"[{datetime.now()}] 检测到表被删除: `{table}`")
                    last_hashes.pop(table, None)
                    if delete_table_sql(table):
                        changes_detected = True
                        changes_info += f"删除表：`{table}`\n"
                
                # 检查现有表的结构变化
                for table in current_tables:
                    current_hash, create_sql = get_table_hash(cursor, table)
                    
                    if table in last_hashes:
                        if last_hashes[table] != current_hash:
                            print(f"[{datetime.now()}] 检测到表结构变化: `{table}`")
                            if save_table_sql(table, create_sql):
                                changes_detected = True
                                changes_info += f"修改表结构：`{table}`\n"
                    
                    last_hashes[table] = current_hash
                
                # 如果有变更，推送到GitHub
                if changes_detected:
                    git_push_changes(changes_info)
                    changes_detected = False
                    changes_info = ''
            else:
                # 首次运行，初始化所有表的SQL文件
                print("首次运行，初始化表结构SQL文件...")
                for table in current_tables:
                    current_hash, create_sql = get_table_hash(cursor, table)
                    last_hashes[table] = current_hash
                    save_table_sql(table, create_sql)
                
                # 首次运行也推送到GitHub
                git_push_changes("首次运行推送")
                
                first_run = False
                print("初始化完成，开始监控表结构变更...")
            
            last_tables = current_tables
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"[{datetime.now()}] 错误: {str(e)}")
        
        time.sleep(interval)

if __name__ == "__main__":
    print("启动MySQL表结构监控...")
    # 检查Git是否已配置
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except:
        print("错误: Git未安装或未配置，自动推送功能将不可用")
    
    monitor_schema_changes(interval=10)