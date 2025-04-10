import mysql.connector
import time
from datetime import datetime
import hashlib
import os
import subprocess
import argparse

def git_push_changes(changes_info, git_repo_path, git_remote, git_branch):
    """将变更推送到GitHub仓库"""
    try:
        # 切换到仓库目录
        os.chdir(git_repo_path)
        
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
        subprocess.run(["git", "push", git_remote, git_branch], check=True)
        
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

def save_table_sql(table_name, sql_content, sql_dir):
    """保存表结构到SQL文件"""
    file_path = os.path.join(sql_dir, f"{table_name}.sql")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(sql_content)
    print(f"已保存表结构到: {file_path}")
    return True  # 返回True表示有变更

def delete_table_sql(table_name, sql_dir):
    """删除表的SQL文件"""
    file_path = os.path.join(sql_dir, f"{table_name}.sql")
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"已删除表结构文件: {file_path}")
        return True  # 返回True表示有变更
    return False

def monitor_schema_changes(config, sql_dir, git_repo_path, git_remote, git_branch, interval=30):
    """监控MySQL表结构变化"""
    
    # 确保sql目录存在
    os.makedirs(sql_dir, exist_ok=True)

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
                    if save_table_sql(table, create_sql, sql_dir):
                        changes_detected = True
                        changes_info += f"创建新表：`{table}`\n"
                
                # 检测被删除的表
                removed_tables = last_tables - current_tables
                for table in removed_tables:
                    print(f"[{datetime.now()}] 检测到表被删除: `{table}`")
                    last_hashes.pop(table, None)
                    if delete_table_sql(table, sql_dir):
                        changes_detected = True
                        changes_info += f"删除表：`{table}`\n"
                
                # 检查现有表的结构变化
                for table in current_tables:
                    current_hash, create_sql = get_table_hash(cursor, table)
                    
                    if table in last_hashes:
                        if last_hashes[table] != current_hash:
                            print(f"[{datetime.now()}] 检测到表结构变化: `{table}`")
                            if save_table_sql(table, create_sql, sql_dir):
                                changes_detected = True
                                changes_info += f"修改表结构：`{table}`\n"
                    
                    last_hashes[table] = current_hash
                
                # 如果有变更，推送到GitHub
                if changes_detected:
                    git_push_changes(changes_info, git_repo_path, git_remote, git_branch)
                    changes_detected = False
                    changes_info = ''
            else:
                # 首次运行，初始化所有表的SQL文件
                print("首次运行，初始化表结构SQL文件...")
                for table in current_tables:
                    current_hash, create_sql = get_table_hash(cursor, table)
                    last_hashes[table] = current_hash
                    save_table_sql(table, create_sql, sql_dir)
                
                # 首次运行也推送到GitHub
                git_push_changes("首次运行推送", git_repo_path, git_remote, git_branch)
                
                first_run = False
                print("初始化完成，开始监控表结构变更...")
            
            last_tables = current_tables
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"[{datetime.now()}] 错误: {str(e)}")
        
        time.sleep(interval)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='MySQL表结构监控工具')
    
    # MySQL配置参数
    parser.add_argument('--db_user', required=True, help='MySQL用户名')
    parser.add_argument('--db_password', required=True, help='MySQL密码')
    parser.add_argument('--db_host', default='localhost', help='MySQL主机')
    parser.add_argument('--db_port', type=int, default=3306, help='MySQL端口')
    parser.add_argument('--db_name', required=True, help='MySQL数据库名')
    
    # 文件存储配置
    parser.add_argument('--sql_dir', default='./sql', help='SQL文件存储目录')
    
    # Git配置
    parser.add_argument('--git_repo_path', default='.', help='Git仓库路径')
    parser.add_argument('--git_remote', default='origin', help='Git远程仓库名称')
    parser.add_argument('--git_branch', default='master', help='Git分支名称')
    
    # 监控配置
    parser.add_argument('--interval', type=int, default=30, 
                       help='监控间隔时间(秒)')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # MySQL配置
    db_config = {
        'user': args.db_user,
        'password': args.db_password,
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name
    }
    
    print("启动MySQL表结构监控...")
    # 检查Git是否已配置
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except:
        print("错误: Git未安装或未配置，自动推送功能将不可用")
    
    monitor_schema_changes(
        config=db_config,
        sql_dir=args.sql_dir,
        git_repo_path=args.git_repo_path,
        git_remote=args.git_remote,
        git_branch=args.git_branch,
        interval=args.interval
    )
"""

python main.py \
    --db_user root \
    --db_password root \
    --db_host localhost \
    --db_port 3306 \
    --db_name ccpc \
    --sql_dir ./sql \
    --git_repo_path . \
    --git_remote origin \
    --git_branch master \
    --interval 5

    python main.py  --db_user root --db_password root --db_host localhost --db_port 3306 --db_name ccpc --sql_dir ./sql --git_repo_path . --git_remote origin --git_branch master --interval 5
"""