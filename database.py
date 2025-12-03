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

# 1. 원본 뉴스 및 수집 로그 관리 (휘발성)
class RawNewsRepo:
    def __init__(self):
        self.db = DBConnection.get_client()["news_archive"]
        self.collection = self.db["origin_news"]
        
        self.collection.create_index("original_link", unique=True)
        self.collection.create_index("collected_at")

    def save_news(self, news_list):
        new_count = 0
        for news in news_list:
            res = self.collection.update_one(
                {"original_link": news["original_link"]},
                {"$set": news},
                upsert=True
            )
            if res.upserted_id: new_count += 1
        return new_count

    def get_recent_news(self, limit=100):
        return list(self.collection.find().sort("collected_at", -1).limit(limit))

    def cleanup_old_news(self, keep_count=100):
        # 최신 순으로 정렬하여 keep_count 번째 문서 찾기
        cursor = self.collection.find().sort("collected_at", -1).skip(keep_count).limit(1)
        doc_list = list(cursor)
        if doc_list:
            threshold_date = doc_list[0]['collected_at']
            # 해당 날짜보다 오래된(작은) 데이터 삭제 
            result = self.collection.delete_many({"collected_at": {"$lt": threshold_date}})
            return result.deleted_count
        return 0

# 2. 학습 자료 및 분석 데이터 관리 (영구 보존)
class LearningRepo:
    def __init__(self):
        self.db = DBConnection.get_client()["news_archive"]
        self.cat_collection = self.db["news_categorized"]   # 분석된 주제 그룹
        self.learn_collection = self.db["learning_materials"] # 생성된 학습 자료
        
        self.cat_collection.create_index("created_at")
        self.learn_collection.create_index("created_at")

    # --- 주제 분류 관련 ---
    def save_topic_groups(self, grouped_data):
        # self.cat_collection.delete_many({}) # 최신 분류만 유지할 경우
        self.cat_collection.insert_one({
            "created_at": datetime.now(),
            "groups": grouped_data
        })

    def get_latest_topics(self):
        return self.cat_collection.find_one(sort=[("created_at", -1)])

    # 분류 데이터도 최신 N개만 유지
    def cleanup_old_topics(self, keep_count=100):
        cursor = self.cat_collection.find().sort("created_at", -1).skip(keep_count).limit(1)
        doc_list = list(cursor)
        if doc_list:
            threshold = doc_list[0]['created_at']
            self.cat_collection.delete_many({"created_at": {"$lt": threshold}})

    # --- 학습 자료 관련 ---
    def save_material(self, data):
        if "_id" in data: del data["_id"]
        return self.learn_collection.insert_one(data)

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

    def update_audio(self, material_id, field, audio_url):
        self.learn_collection.update_one(
            {"id": material_id},
            {"$set": {field: audio_url}}
        )

    def delete_material(self, material_id):
        return self.learn_collection.delete_one({"id": material_id}).deleted_count

