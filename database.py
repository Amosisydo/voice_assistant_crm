import sqlite3
import logging
import json
from typing import List, Dict, Tuple, Optional
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

def init_database():
    """初始化扩展的SQLite数据库"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 用户表（保留）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            name TEXT,
            email TEXT,
            preferred_channel TEXT DEFAULT 'text',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 扩展的对话记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel TEXT DEFAULT 'text',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            audio_path TEXT,
            intent TEXT,
            metadata TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # 用户偏好表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            preference_key TEXT NOT NULL,
            preference_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, preference_key)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("数据库初始化完成")

class UserManager:
    def __init__(self):
        self.db_path = DATABASE_PATH
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def get_or_create_user(self, phone_number: str, channel: str = 'text') -> Tuple[int, bool]:
        """获取或创建用户，支持指定渠道偏好"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, preferred_channel FROM users WHERE phone_number = ?', (phone_number,))
        result = cursor.fetchone()
        
        if result:
            user_id = result[0]
            # 更新渠道偏好
            if channel != result[1]:
                cursor.execute(
                    'UPDATE users SET preferred_channel = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (channel, user_id)
                )
            is_new = False
        else:
            # 创建新用户
            cursor.execute(
                'INSERT INTO users (phone_number, preferred_channel) VALUES (?, ?)',
                (phone_number, channel)
            )
            user_id = cursor.lastrowid
            is_new = True
            
            # 记录初始对话
            cursor.execute(
                'INSERT INTO conversations (user_id, channel, role, content) VALUES (?, ?, ?, ?)',
                (user_id, channel, 'system', f'新用户通过{channel}渠道注册')
            )
        
        conn.commit()
        conn.close()
        logger.info(f"用户管理: phone={phone_number}, user_id={user_id}, is_new={is_new}, channel={channel}")
        return user_id, is_new
    
    def get_user_conversations(self, user_id: int, limit: int = 10) -> List[Dict]:
        """获取用户对话历史"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role, content, intent, timestamp, channel, metadata
            FROM conversations 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))
        
        conversations = []
        for row in cursor.fetchall():
            metadata = {}
            if row[5]:
                try:
                    metadata = json.loads(row[5])
                except:
                    metadata = {}
            
            conversations.append({
                'role': row[0],
                'content': row[1],
                'intent': row[2],
                'timestamp': row[3],
                'channel': row[4] or 'text',
                'metadata': metadata
            })
        
        conn.close()
        return conversations[::-1]  # 反转以得到时间正序
    
    def add_conversation(self, user_id: int, channel: str, role: str, content: str, 
                        intent: str = None, audio_path: str = None, metadata: dict = None):
        """添加对话记录，支持语音和文本"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        metadata_str = None
        if metadata:
            metadata_str = json.dumps(metadata)
        
        cursor.execute(
            '''INSERT INTO conversations 
               (user_id, channel, role, content, intent, audio_path, metadata) 
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, channel, role, content, intent, audio_path, metadata_str)
        )
        
        # 更新用户最后活跃时间
        cursor.execute(
            'UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (user_id,)
        )
        
        conn.commit()
        conn.close()
        logger.info(f"添加对话记录: user_id={user_id}, role={role}, channel={channel}, intent={intent}")
    
    def update_user_profile(self, user_id: int, key: str, value: str):
        """更新用户信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_profiles (user_id, preference_key, preference_value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, key, value))
        
        conn.commit()
        conn.close()
        logger.info(f"更新用户资料: user_id={user_id}, {key}={value}")