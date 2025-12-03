import os
from pymongo import MongoClient
from datetime import datetime
import dotenv
import certifi

dotenv.load_dotenv()

class DBConnection:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
            # 클라우드 환경의 SSL 인증서 문제를 해결하기 위해 certifi 옵션 추가
            cls._client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
        return cls._client

# 2. 학습 자료 및 분석 데이터 관리 (영구 보존)
class LearningRepo:
    def __init__(self):
        self.db = DBConnection.get_client()["news_archive"]
        self.cat_collection = self.db["news_categorized"]   # 분석된 주제 그룹
        self.learn_collection = self.db["learning_materials"] # 생성된 학습 자료

    def get_latest_topics(self):
        return self.cat_collection.find_one(sort=[("created_at", -1)])

    # 전체 데이터 개수 조회 (총 페이지 수 계산용)
    def count_materials(self):
        return self.learn_collection.count_documents({})
    
    # 페이지네이션 지원 (page 번호와 page_size를 받음)
    def get_materials(self, page=1, page_size=50):
        skip_count = (page - 1) * page_size
        return list(self.learn_collection.find()
                    .sort("created_at", -1)
                    .skip(skip_count)
                    .limit(page_size))
