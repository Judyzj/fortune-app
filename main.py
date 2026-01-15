"""
FastAPI 命理应用后端
提供八字排盘和命理分析 API
"""
import os
import json
import re
import base64
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from calculator import FortuneCalculator
from services.lifeline import lifeline_service
from services.lifeline import lifeline_service

# 加载环境变量
load_dotenv()

# 数据库配置
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fortune_app.db")
# SQLite 需要 check_same_thread，PostgreSQL 不需要
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 数据库模型
class FortuneBook(Base):
    """命书记录表"""
    __tablename__ = "fortune_books"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default_user")  # 用户ID（从Session或JWT获取）
    name = Column(String, nullable=False)  # 命书名（用户自定义）
    person_name = Column(String, nullable=False)  # 姓名
    birth_date = Column(String, nullable=False)  # 出生日期 YYYY-MM-DD
    birth_time = Column(String, nullable=False)  # 出生时间 HH:MM
    gender = Column(String, nullable=False)  # 性别
    lat = Column(Float, nullable=False)  # 纬度
    lng = Column(Float, nullable=False)  # 经度
    city = Column(String, nullable=False)  # 城市
    summary = Column(Text, nullable=True)  # 大模型生成的JSON内容全文（存储完整的bazi_report和llm_data）
    analysis_result = Column(Text, nullable=True)  # 排盘数据JSON（日元、十神、五行、喜用神、建议等）
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "person_name": self.person_name,
            "birth_details": f"{self.person_name}，{self.birth_date} {self.birth_time}，{self.city}"
        }
    
    def to_dict_with_id(self):
        """转换为字典（包含完整信息，用于返回保存结果）"""
        return {
            "id": self.id,
            "name": self.name,
            "person_name": self.person_name,
            "birth_date": self.birth_date,
            "birth_time": self.birth_time,
            "gender": self.gender,
            "city": self.city,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 检查并添加 analysis_result 字段（如果不存在）
def ensure_analysis_result_column():
    """确保 analysis_result 字段存在"""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if 'fortune_books' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('fortune_books')]
        if 'analysis_result' not in columns:
            print("添加 analysis_result 字段到 fortune_books 表...", flush=True)
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE fortune_books ADD COLUMN analysis_result TEXT'))
                conn.commit()
            print("✅ analysis_result 字段已添加", flush=True)
        else:
            print("✅ analysis_result 字段已存在", flush=True)

# 确保字段存在
ensure_analysis_result_column()

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# JWT Token 解析（简化版，生产环境应使用完整的 JWT 库如 PyJWT）
def get_current_user_id(
    authorization: Optional[str] = Header(None),
    user_id: Optional[str] = None
) -> str:
    """
    从请求头中获取用户ID
    
    优先级：
    1. 从 Authorization header 中解析 JWT token（如果存在）
    2. 从 query 参数 user_id 获取（开发/测试用）
    3. 使用环境变量中的默认用户ID（仅开发环境）
    4. 使用 "default_user"（仅开发环境，不安全）
    
    生产环境必须使用 JWT token 进行身份验证
    """
    # 1. 尝试从 Authorization header 解析 JWT token
    if authorization:
        try:
            # 移除 "Bearer " 前缀（如果存在）
            token = authorization.replace("Bearer ", "").strip()
            
            # 简化版 JWT 解析（仅用于开发环境）
            # 生产环境应使用 PyJWT 库进行完整验证
            # 例如：import jwt
            #      payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            #      return payload.get("user_id")
            
            # 这里使用简单的 base64 解码（仅用于开发环境演示）
            # 注意：这不是真正的 JWT 验证，仅用于演示
            if token and len(token) > 10:  # 简单检查
                # 尝试解析 token（假设 token 格式为 base64 编码的 JSON）
                try:
                    # 如果是 base64 编码的 JSON
                    decoded = base64.b64decode(token + "==").decode('utf-8')
                    token_data = json.loads(decoded)
                    if "user_id" in token_data:
                        user_id_from_token = token_data["user_id"]
                        print(f"✅ 从 JWT token 解析用户ID: {user_id_from_token}", flush=True)
                        return user_id_from_token
                except:
                    # 如果不是 base64，尝试直接使用 token 作为 user_id（仅开发环境）
                    if os.getenv("ENV") == "development":
                        print(f"⚠️  开发环境：直接使用 token 作为 user_id", flush=True)
                        return token[:50]  # 限制长度
        except Exception as e:
            print(f"⚠️  JWT token 解析失败: {e}，使用默认用户ID", flush=True)
    
    # 2. 从 query 参数获取（开发/测试用）
    if user_id:
        print(f"✅ 从 query 参数获取用户ID: {user_id}", flush=True)
        return user_id
    
    # 3. 从环境变量获取默认用户ID（仅开发环境）
    default_user_id = os.getenv("DEFAULT_USER_ID")
    if default_user_id and os.getenv("ENV") == "development":
        print(f"⚠️  开发环境：使用环境变量中的默认用户ID: {default_user_id}", flush=True)
        return default_user_id
    
    # 4. 使用 "default_user"（仅开发环境，不安全）
    env = os.getenv("ENV", "development")
    if env == "production":
        # 生产环境：如果没有提供有效的身份信息，返回 401
        # 但为了内网环境的兼容性，允许使用 IP + User-Agent 生成临时用户ID
        # 注意：这不是真正的身份验证，仅用于内网环境下的用户隔离
        from fastapi import Request
        # 这里需要从请求中获取 Request 对象，但当前函数签名不支持
        # 所以生产环境仍然要求提供 token
        raise HTTPException(
            status_code=401,
            detail="生产环境必须提供有效的身份验证信息（JWT token 或 user_id）"
        )
    else:
        print(f"⚠️  开发环境：使用默认用户ID 'default_user'（不安全，仅用于开发）", flush=True)
        return "default_user"

app = FastAPI(title="命理分析 API", version="1.0.0")

# 配置 CORS
# 从环境变量读取允许的域名，开发环境默认允许所有，生产环境应设置具体域名
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",") if os.getenv("ALLOWED_ORIGINS") else ["*"]
# 如果设置了 ALLOWED_ORIGINS 环境变量，使用该值；否则在开发环境允许所有
if os.getenv("ALLOWED_ORIGINS"):
    # 生产环境：使用环境变量中配置的具体域名
    allowed_origins = [origin.strip() for origin in ALLOWED_ORIGINS]
    print(f"🔒 CORS 配置：生产模式，允许的域名: {allowed_origins}", flush=True)
else:
    # 开发环境：允许所有（仅用于本地开发）
    allowed_origins = ["*"]
    print(f"⚠️  CORS 配置：开发模式，允许所有域名（生产环境请设置 ALLOWED_ORIGINS 环境变量）", flush=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化计算器和 AI 客户端
calculator = FortuneCalculator()
compass_client = None
deepseek_api_key = None
deepseek_base_url = None

# 加载环境变量
COMPASS_API_KEY = os.getenv("COMPASS_API_KEY", "")
COMPASS_BASE_URL = os.getenv("COMPASS_BASE_URL", "https://compass.llm.shopee.io/compass-api/v1")

# 初始化 Compass 客户端
if COMPASS_API_KEY:
    try:
        compass_client = genai.Client(
            api_key=COMPASS_API_KEY,
            http_options=types.HttpOptions(
                api_version='v1',
                base_url=COMPASS_BASE_URL,
            )
        )
        print("✅ Compass API 客户端初始化成功", flush=True)
    except Exception as e:
        print(f"⚠️  Compass API 客户端初始化失败: {e}", flush=True)
        compass_client = None

# 初始化 DeepSeek API 配置（作为备用）
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
deepseek_base_url = os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com/v1")
if deepseek_api_key:
    print("✅ DeepSeek API 已配置（作为备用）", flush=True)
else:
    print("⚠️  DeepSeek API 未配置", flush=True)

# 加载知识库
FAQ_CONTENT = ""
FAQ_PATH = "faq.txt"
try:
    if os.path.exists(FAQ_PATH):
        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            FAQ_CONTENT = f.read()
    else:
        print(f"⚠️  知识库文件 {FAQ_PATH} 不存在，将使用空知识库")
except Exception as e:
    print(f"⚠️  读取知识库文件 {FAQ_PATH} 失败: {e}，将使用空知识库")
    FAQ_CONTENT = ""

# 起卦对话 System Prompt（单轮深度交付版）
DIVINATION_SYSTEM_PROMPT = """你是一位实战派命理顾问，擅长将复杂的八字、紫微斗数转化为现代人的"人生避坑指南"。

**你的任务：** 用户只有一次提问机会。你必须在这一次回复中，基于用户的生辰八字，交付一份完整、深刻、且极具个性化的命理分析报告。

你的语言风格：专业、直白、不啰嗦，像一份价值千金的商业咨询报告。拒绝玄学黑话，用通俗易懂的大白话解释命理。

【核心原则】
1. **不知生辰，不敢妄断**：当用户初次咨询时，必须引导用户提供完整的生辰信息（出生年月日、时辰、性别、出生地）。
2. **单轮完整输出**：一旦用户提供生辰信息，立即按完整结构输出，**严禁分段，严禁引导追问**。
3. **去玄学化**：不说"食神、伤官"，说"才华、反叛精神"；不说"寅申冲"，说"环境变动、车马之劳"。
4. **拒绝宽泛**：禁止使用"性格开朗"、"事业有成"等废话。必须结合八字（如：火旺则急、土重则厚）给出具体的描述。

【阶段1：初始接待 (Greeting)】

**情况A：普通命理咨询**
- 当用户初次点击时，自称"AI算命·命理先知"。
- 问候："有缘人，你好。"
- 说明原则："起卦需严谨，不知生辰，不敢妄断。"
- 引导用户提供完整信息，使用以下话术：
  "请提供以下信息以便进行精准测算：
  
  1. 出生年月日时（公历）及性别。
  2. 时辰（尽量精确，如：上午9点、下午3点30分等）。
  3. 出生地（城市名称即可）。
  4. 想要问的具体问题（例如：我的论文是否能被期刊XX录取？）。
  5. 此时此刻的北京时间。
  6. 脑海中第一时间浮现的三个数字。
  
  待你提供完整信息后，我当为你排盘推演，解析命理。"
- 此时不要进行任何分析。

**情况B：论文投稿起卦（检测关键词：论文、paper、投稿、中稿、发表等）**
- 当用户提到论文、投稿等相关问题时，立即识别为"论文投稿起卦"需求。
- **用户只有一次提问机会，必须一次性引导用户提供所有信息**。
- 引导话术示例：
  "好的，我来帮你用梅花易数、奇门遁甲和小六壬三种方式测算论文能否中稿。请一次性提供以下信息：
  
  1. **论文投稿时间**：XX年X月X日（例如：2025年3月15日）
  2. **你的八字**：XX XX XX XX（例如：庚辰 戊子 丙戌 癸巳），以及对应的公历生日（例如：2000年11月12日）
  3. **当前时间**：2026年X月X日X点XX分（例如：2026年1月20日14点30分）
  4. **三个数字**：请告诉我你脑海中第一时间浮现的三个数字（例如：3、7、9）
  
  请按照以上格式一次性提供，我会立即为你起卦测算。"
  
- **起卦测算流程**（当用户提供完整信息后）：
  1. **梅花易数测算**：
     - 使用用户提供的三个数字起卦
     - 分析卦象，判断论文中稿的可能性
     - 用大白话解释：能中/不能中/有风险，原因是什么
  2. **奇门遁甲测算**：
     - 根据投稿时间和当前时间起局
     - 分析论文投稿的吉凶
     - 指出关键时间节点和注意事项
  3. **小六壬测算**：
     - 使用三个数字进行小六壬推算
     - 得出最终结果：大安/留连/速喜/赤口/小吉/空亡
     - 解释该结果对论文中稿的预示
  4. **综合结论**：
     - 综合三种方法的结果
     - 给出最终判断：能中/不能中/有风险
     - 提供3条具体建议（例如：修改方向、投稿时机、注意事项）
  
- **输出格式要求**：
  - 使用清晰的标题：**【梅花易数】**【奇门遁甲】**【小六壬】**【综合结论】
  - 每个方法用大白话解释，拒绝玄学黑话
  - 总字数控制在400字以内
  - 结论要直接、明确

【阶段2：单轮完整输出 (拿到生辰后)】

**重要：用户只有一次提问机会。一旦用户提供生辰信息，立即按以下完整结构输出，严禁分段，严禁引导追问。**

#### 1. 【核心能量配置】 (开门见山)
- **排盘**：列表展示年、月、日、时四柱及日主。
- **格局定性**：直接指出属于什么格局（如：杀印相生、食神生财等），日主强弱及最核心的喜用神。
- **一句话点破命局**：用最犀利的一句话总结此命造的最高成就或最大短板。

#### 2. 【五大维度深度拆解】 (个性化分析，每项100-150字)
- **🧑 个性与潜能**：基于十神心性，分析用户不易察觉的性格侧面。不说空话，要说出"为什么我会这样"。
- **💼 事业与阶层**：明确适合的行业（如：创意、管理、公职等），指出职业天花板在哪里，以及最适合的发展方向。
- **💰 财富与段位**：分析财运厚薄。是靠体力、技术还是眼光赚钱？指出一生中容易破财的风险点。
- **❤️ 情感与家庭**：描述配偶的大致性格特征，给出具体的结婚建议（早/晚），以及如何处理感情中的冲突。
- **🏥 身体与风水**：根据五行缺失，指出未来 10-20 年最需要防范的脏腑问题，并给出 1 个简单的居家风水调节建议。

#### 3. 【未来运势与转折点】 (大运流年)
- **当前大运分析**：详细解析用户目前正在走的这 10 年大运（150-200字）。直接指出核心机会（该进取还是该守成）及潜在风险。
- **未来 3 年流年预警**：基于当前年份分析接下来三年（当前年、明年、后年）的运势高低，标注出哪一年是"关键转运年"。

#### 4. 【人生锦囊】 (实战建议)
- 给出 3 条**不讲玄学、只讲实战**的建议。例如：
  - "你这种命局，今年 10 月前绝不能辞职。"
  - "你的配偶宫被冲，沟通时多听少说，能避开 80% 的矛盾。"

【输出风格规则】
1. **去玄学化**：
   - ❌ 不说"食神、伤官"，✅ 说"才华、反叛精神"
   - ❌ 不说"寅申冲"，✅ 说"环境变动、车马之劳"
   - ❌ 不说"财多身弱"，✅ 说"赚钱虽然多，但容易透支身体"
2. **拒绝宽泛**：禁止使用"性格开朗"、"事业有成"等废话。必须结合八字（如：火旺则急、土重则厚）给出具体的描述。
3. **结构化视觉**：大量使用 **加粗**、Markdown 表格和引用块（>），使长文依然易于阅读。
4. **语气要求**：专业、直白、不啰嗦，像一份价值千金的商业咨询报告。
"""

# 简短指令（用于后续对话）
DIVINATION_CONTINUE_PROMPT = """请基于以上命盘上下文继续回答，禁止重复输出排盘和基本面分析。

如果用户询问具体问题（如起大运、看事业、看姻缘等），请直接回答，用大白话解释，拒绝玄学黑话。

输出要求：
1. **直给结论**：第一句话就回答用户最关心的事（能成/不能成/风险在哪）。
2. **逻辑支撑**：用大白话解释原因，拒绝玄学黑话。
3. **避坑指南**：给出 3 条具体的、今天就能做的建议。

语气要求：专业、直白、不啰嗦，像一份价值千金的商业咨询报告。"""

# 单一事件起卦 System Prompt（重构版：翻译官模式，拒绝死局，更有温度）
SINGLE_EVENT_DIVINATION_PROMPT = """### Role Definition
你是一位深谙易学与现代心理学的"AI 易学顾问"。
**你的核心价值观：** 易学不是为了宣判宿命，而是为了以此推演事物发展的规律，帮人趋吉避凶。
**你的语言风格：** 通俗易懂，专业但不枯燥，客观但不冷漠。你总是能从不利的卦象中找到"一线生机"或"改进方向"。

### Interaction Protocol (单轮深度交付)

当用户提供起卦信息（时间、数字、问题）后，请按以下逻辑进行推演，并严格遵守输出格式：

#### 情况 A：信息不全
如果用户没有提供以下完整信息，请以"起卦需严谨"为由，简洁列出以下清单并停止输出：
1. 出生年月日时（公历）及性别。
2. 想要问的具体问题。
3. 此时此刻的北京时间。
4. 脑海中第一时间浮现的三个数字。

#### 情况 B：信息齐全 (深度交付模式)

#### 1. 【直观结论：局势研判】 (开篇点题)
- **核心回答**：不要直接给冷冰冰的概率数字。用定性的描述回答用户（如："前路虽有迷雾，但并非无解"、"目前时机尚早，需静待花开"）。
- **难度评级**：使用 ★★★☆☆ 形式展示"达成难度"或"阻力指数"，替代绝对的成功率。
- **一句话摘要**：用通俗的语言概括目前的处境（例如："你很急切，但对方或环境还未准备好"）。

#### 2. 【卦象解码：透视现象】 (专业+通俗)
在此板块，你需要列出专业术语，但必须紧跟**"人话翻译"**。
- **小六壬（看时机）**：
  - 输出格式：`课位名称` —— `通俗解释`。
  - *示例：* "留连 —— 意思是'拖延、缓慢'。说明这件事不会像你预期的那样快，需要多一点耐心。"
- **梅花易数（看过程）**：
  - 展示主卦、变卦名称。
  - **重点解释体用关系**：不要只说"用克体"，要解释为"外部环境对你构成了压力/这件事的主导权暂时不在你手里"。
  - **卦意映射**：将"无妄"、"讼"等卦名翻译成具体场景。如"讼"代表"观点不合、需要大量沟通"，而不是"打官司"。
- **奇门/神煞（看细节）**：
  - 选取 1-2 个最关键的符号进行解读。
  - *转化技巧*：遇到"死门/惊门"，解释为"对方态度不够积极"或"容易产生误会"；遇到"玄武"，解释为"局势不明朗，信息不对称"。

#### 3. 【转机与锦囊：怎么做？】 (核心价值)
这是最重要的部分。基于卦象中的"变爻"或"生门"方向，给出**可操作**的建议。
- **心态调整**：基于卦象建议用户该"进取"还是"蛰伏"。
- **具体行动**：
  - 如果卦象显示"口舌"，建议："多倾听，少争辩，避免在情绪上头时做决定。"
  - 如果卦象显示"阻滞"，建议："先把重心放回自己身上，未来 3 个月不宜主动出击。"
- **有利时机**：根据卦象指出下一个有利的时间窗口（如"等到秋天金旺之时"）。

### Output Style Rules (避坑指南)
1. **严禁绝对化**：禁止使用"绝无可能"、"必定失败"、"定有灾祸"等词汇。改用"阻力较大"、"挑战明显"、"需付出双倍努力"。
2. **术语软化**：
  - "官鬼/官非" -> 转化为 "压力、竞争、由于沟通引发的争执"。
  - "死门/空亡" -> 转化为 "暂时停滞、对方没想好、力不从心"。
3. **排版要求**：使用引用块（>）高亮核心结论，使用列表整理建议，确保易读性。
"""


class FortuneRequest(BaseModel):
    """命理分析请求模型"""
    name: str
    gender: str
    birth_date: str  # 格式: YYYY-MM-DD
    birth_time: str  # 格式: HH:MM
    lat: float
    lng: float
    city: str
    auto_save: Optional[bool] = False  # 是否自动保存到数据库
    book_name: Optional[str] = None  # 命书名（如果auto_save=True，必须提供）

    @field_validator('birth_date')
    @classmethod
    def validate_birth_date(cls, v: str) -> str:
        """验证出生日期格式和有效性"""
        if not v:
            raise ValueError('出生日期不能为空')
        
        # 验证格式 YYYY-MM-DD
        try:
            date_obj = datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('出生日期格式错误，应为 YYYY-MM-DD（如：2000-10-10）')
        
        # 验证年份范围
        year = date_obj.year
        if year < 1900 or year > 2100:
            raise ValueError('年份范围应在1900-2100之间')
        
        # 验证月份范围（datetime 已经验证了，但为了明确性）
        month = date_obj.month
        if month < 1 or month > 12:
            raise ValueError('月份范围应在1-12之间')
        
        # 验证日期范围（datetime 已经验证了日期有效性，包括闰年、月份天数等）
        day = date_obj.day
        if day < 1 or day > 31:
            raise ValueError('日期范围应在1-31之间')
        
        # 验证日期是否真实存在（例如：2月30日会被 datetime 拒绝）
        # datetime.strptime 已经处理了这一点，如果日期无效会抛出 ValueError
        
        return v

class KLineGenerateRequest(BaseModel):
    """K线生成请求模型（支持两种入参方式）"""
    book_id: Optional[int] = None  # 情况1：传 book_id
    # 情况2：传 birth_data（如果没有 book_id）
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    birth_time: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    city: Optional[str] = None
    
    @field_validator('birth_date')
    @classmethod
    def validate_birth_date_if_provided(cls, v):
        """如果提供了 birth_date，验证格式"""
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('出生日期格式错误，应为 YYYY-MM-DD（如：2000-10-10）')
        return v


class SaveFortuneBookRequest(BaseModel):
    """保存命书请求模型"""
    name: str  # 命书名（用户自定义）
    person_name: str  # 姓名
    gender: str  # 性别
    birth_date: str  # 出生日期 YYYY-MM-DD
    birth_time: str  # 出生时间 HH:MM
    lat: float  # 纬度
    lng: float  # 经度
    city: str  # 城市
    analysis_result: Optional[dict] = None  # 排盘数据（日元、十神、五行、喜用神、建议等，可选）- 类型为 dict，FastAPI 会自动解析 JSON 字符串
    summary: Optional[str] = None  # 大模型生成的JSON内容全文（可选）
    
    @field_validator('birth_date')
    @classmethod
    def validate_birth_date(cls, v: str) -> str:
        """验证出生日期格式和有效性"""
        if not v:
            raise ValueError('出生日期不能为空')
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('出生日期格式错误，应为 YYYY-MM-DD（如：2000-10-10）')
        return v


    @field_validator('birth_time')
    @classmethod
    def validate_birth_time(cls, v: str, info) -> str:
        """
        验证出生时间格式和有效性
        
        特别注意：早子时/晚子时问题
        - 23:00-00:59 属于晚子时（当天）
        - 00:00-00:59 属于早子时（次日）
        - 如果用户输入的是 23:00 或 00:00，需要确保日期计算正确
        """
        if not v:
            raise ValueError('出生时间不能为空')
        
        # 处理分钟为空的情况：如果格式是 "HH:" 或 "HH"，自动补全为 "HH:00"
        if v.endswith(':') or (':' not in v and v.isdigit()):
            # 如果只有小时，补全分钟为 00
            if ':' in v:
                hour_part = v.rstrip(':')
            else:
                hour_part = v
            try:
                hour = int(hour_part)
                if 0 <= hour <= 23:
                    v = f"{hour:02d}:00"
                else:
                    raise ValueError('小时范围应在0-23之间')
            except ValueError:
                raise ValueError('出生时间格式错误，应为 HH:MM（如：12:00 或 14:30）或仅小时（如：12，将自动补全为 12:00）')
        
        # 验证格式 HH:MM
        try:
            time_obj = datetime.strptime(v, '%H:%M')
        except ValueError:
            raise ValueError('出生时间格式错误，应为 HH:MM（如：12:00 或 14:30）')
        
        # 验证小时范围
        hour = time_obj.hour
        minute = time_obj.minute
        
        # 早子时/晚子时边界检查
        # 注意：23:00-00:59 属于晚子时（当天），00:00-00:59 属于早子时（次日）
        # 如果用户输入的是 23:00 或 00:00，需要确保日期计算正确
        # 这个边界问题在 calculator.py 中需要特别处理
        if hour == 23 or (hour == 0 and minute == 0):
            # 警告：边界时间需要特别注意日期计算
            # 23:00 属于当天晚子时，但可能影响次日日柱计算
            # 00:00 属于次日早子时，需要确保日期正确
            pass  # 这里只做验证，实际日期计算在 calculator.py 中处理
        
        if hour < 0 or hour > 23:
            raise ValueError('小时范围应在0-23之间')
        
        # 验证分钟范围（允许00，如12:00）
        minute = time_obj.minute
        if minute < 0 or minute > 59:
            raise ValueError('分钟范围应在0-59之间（如：12:00 中的 00 是允许的）')
        
        return v


def build_system_prompt(bazi_report: dict, name: str, gender: str, city: str) -> str:
    """
    构建系统提示词（升级版：包含硬核判定和核心性格语料库）
    
    Args:
        bazi_report: BaziReport 数据结构
        name: 姓名
        gender: 性别
        city: 城市
    
    Returns:
        系统提示词字符串
    """
    chart = bazi_report['chart']
    five_elements = bazi_report.get('five_elements_legacy', bazi_report.get('five_elements', {}))
    gods = bazi_report['gods']
    da_yun = bazi_report['da_yun']
    
    # 提取关键数据
    day_master = bazi_report.get('day_master', chart.get('day_gan', ''))
    day_wuxing = gods.get('day_wuxing', '')
    strength_status = gods.get('strength_status', '中和')
    pattern_name = gods.get('pattern_name', '正格')
    yong_shen = gods.get('useful_gods', [])
    xi_shen = gods.get('favorable_god', '')
    personality_tags = gods.get('personality_tags', [])
    
    # 五行百分比（兼容新旧格式）
    if isinstance(five_elements, list):
        # 新格式：数组
        wuxing_percentages = {elem['name']: elem['percent'] for elem in five_elements}
    else:
        # 旧格式：字典
        wuxing_percentages = five_elements.get('percentages', {})
    
    mu = wuxing_percentages.get('木', 0)
    huo = wuxing_percentages.get('火', 0)
    tu = wuxing_percentages.get('土', 0)
    jin = wuxing_percentages.get('金', 0)
    shui = wuxing_percentages.get('水', 0)
    
    # 1. 系统角色定义
    role_prompt = """你是一位精通子平八字与现代心理学的命理专家。你的任务是基于后端提供的"精密排盘数据"，为用户提供温暖、治愈且富有深度的命理分析。

要求：
- 语气：专业、儒雅、鼓励性，避免恐吓式断命
- 逻辑：严格遵守后端给出的日主强弱、喜用神和五行得分，不得随意更改基本事实
- 风格：将生涩的术语（如"伤官见官"）转化为易懂的生活建议和性格解析"""
    
    # 2. 后端注入的"事实语料库"
    facts = f"""
[核心数据]
- 日主：{day_master}（{day_wuxing}）
- 状态：{strength_status}（如：日主中和/强/弱）
- 格局：{pattern_name}
- 喜用神：{', '.join(yong_shen) if yong_shen else '无'}、{xi_shen if xi_shen else ''}
- 五行能量：木({mu}%), 火({huo}%), 土({tu}%), 金({jin}%), 水({shui}%)
- 性格标签：{', '.join(personality_tags) if personality_tags else '无'}
"""
    
    # 3. 核心性格语料库
    personality_knowledge = """
[核心性格语料库]
根据日主天干和五行，参考以下性格特征进行准确分析：

- 丙火：像夏日的阳光，热情洋溢，充满感染力。性格外向开朗，善于表达和沟通，能够激励和影响他人。
- 辛金：像温润的珠宝，外柔内刚，心思细腻。讲究品质感，自尊心强，具备极强的毅力和自我雕琢精神。
- 壬水：像奔腾的大海，聪明灵动，格局宏大。适应能力极强，思维活跃，带有一种与生俱来的自由气息。
- 戊土：像厚重的大地，诚实稳重，包容力强。值得信赖，做事脚踏实地，但有时略显固执。
- 甲木：像参天大树，正直向上，有领导力。积极进取，有开拓精神，但有时过于刚直。
- 乙木：像柔韧的藤蔓，温和细腻，有韧性。适应力强，善于变通，但有时缺乏主见。
- 丁火：像温暖的烛光，细致温暖，有耐心。善于照顾他人，有艺术天赋，但有时过于敏感。
- 己土：像肥沃的土壤，温和包容，有责任感。踏实可靠，善于协调，但有时过于保守。
- 庚金：像锋利的刀剑，刚强果断，有原则。意志坚定，执行力强，但有时过于刚硬。
- 癸水：像清澈的溪流，温柔智慧，适应力强。思维敏捷，善于学习，但有时过于随波逐流。
"""
    
    # 八字排盘数据（详细版）
    bazi_data = f"""
【八字排盘数据（BaziReport）】
姓名: {name}
性别: {gender}
出生地: {city}
真太阳时: {bazi_report['true_solar_time']}

四柱八字详情:
"""
    for pillar in chart['pillars']:
        bazi_data += f"  {pillar['name']}: {pillar['gan_zhi']} "
        bazi_data += f"(天干:{pillar['gan']}{pillar['gan_wuxing']}, 地支:{pillar['zhi']}{pillar['zhi_wuxing']})"
        if pillar['cang_gan']:
            cang_str = ', '.join([f"{c['gan']}({c['score']}分)" for c in pillar['cang_gan']])
            bazi_data += f" 藏干:[{cang_str}]"
        if pillar['na_yin']:
            bazi_data += f" 纳音:{pillar['na_yin']}"
        bazi_data += "\n"
    
    bazi_data += f"\n十神配置:\n"
    for key, value in chart['shi_shen'].items():
        pillar_name = key.replace('_shi_shen', '').replace('year', '年柱').replace('month', '月柱').replace('day', '日柱').replace('hour', '时柱')
        bazi_data += f"  {pillar_name}: {value}\n"
    
    bazi_data += f"\n日主: {chart['day_gan']}{chart['day_zhi']} ({gods['day_wuxing']})\n"
    
    # 五行能量分析
    bazi_data += f"""
【五行能量分析】
五行得分: 木={five_elements['scores']['木']}, 火={five_elements['scores']['火']}, 土={five_elements['scores']['土']}, 金={five_elements['scores']['金']}, 水={five_elements['scores']['水']}
五行占比: 木={five_elements['percentages']['木']}%, 火={five_elements['percentages']['火']}%, 土={five_elements['percentages']['土']}%, 金={five_elements['percentages']['金']}%, 水={five_elements['percentages']['水']}%
最旺五行: {five_elements['strongest']}
最弱五行: {five_elements['weakest']}
五行状态: {five_elements['missing']}

【用神分析】
日主强弱: {'偏强' if gods['is_strong'] else '偏弱'}
同党得分: {gods['tong_dang_score']} (印、比劫)
异党得分: {gods['yi_dang_score']} (食伤、财、官杀)
喜用神: {', '.join(gods['useful_gods']) if gods['useful_gods'] else '无'}
忌神: {', '.join(gods['taboo_gods']) if gods['taboo_gods'] else '无'}

大运:
"""
    for dy in da_yun:
        bazi_data += f"  {dy['age_start']}-{dy['age_end']}岁: {dy['gan_zhi']}\n"
    
    # 知识库内容
    knowledge_base = f"""
【知识库参考】
{FAQ_CONTENT}
"""
    
    # 输出要求
    output_requirements = f"""
【重要提示】
1. 必须严格基于上述"核心数据"中的事实进行分析，不得随意猜测或编造干支信息
2. 日主强弱、格局、喜用神等关键信息已由后端精确计算，请直接使用，不要重新计算
3. 性格分析请参考"核心性格语料库"，结合日主天干和格局进行准确描述
4. 必须生成"性格特质"标签（如：热情、光明、积极），这些标签将用于前端UI展示
5. 必须生成"命理精华"文本，这是对日主和性格的总结性描述（如："日主丙,五行属火。性格如夏火般热情洋溢,充满活力和感染力,善于激励他人。"）

【输出要求】
【输出要求】
1. 首先根据上述 BaziReport 数据，提供详细的命理分析（流式输出纯文本），必须包括：

   **性格与天赋分析**（重点）：
   - 基于五行能量分布和用神分析，深入解读性格特点
   - 结合十神配置，分析天赋才能和潜在优势
   - 用现代心理学语言，解释传统命理概念
   - 例如：如果五行缺金，可以分析"缺乏决断力、容易优柔寡断"等性格特征
   - 例如：如果喜用神为水，可以分析"适合从事需要智慧和灵活性的工作"等天赋方向

   **核心十神解读**（重点）：
   - 详细分析四柱中的十神配置
   - 解释每个十神对性格和命运的影响
   - 结合现代心理学，给出行为模式分析
   - 例如：正官多的人"有责任感、遵守规则"，七杀多的人"有魄力、敢于冒险"等

   **其他分析**：
   - 事业运势分析（结合用神和五行）
   - 感情婚姻分析
   - 财运分析
   - 健康建议（结合五行缺失）
   - 人生建议（结合用神方向）

2. 在分析的最后，必须包含一个 JSON 数据块，格式如下：
<<<CHART_DATA>>>
{{
  "career": [20-60岁各年龄的事业评分，0-100],
  "relationship": [20-60岁各年龄的感情评分，0-100],
  "wealth": [20-60岁各年龄的财运评分，0-100]
}}
<<<CHART_DATA>>>

注意：JSON 数据块必须严格按照上述格式，包含41个数据点（20岁到60岁，共41年）。

3. 分析时请充分利用 BaziReport 中的硬数据（五行得分、用神、十神等），确保分析有数据支撑，而不是泛泛而谈。
"""
    
    return f"{role_prompt}\n\n{facts}\n\n{personality_knowledge}\n\n{bazi_data}\n\n{knowledge_base}\n\n{output_requirements}"


def parse_llm_json_response(text: str) -> Optional[dict]:
    """
    解析 LLM 返回的 JSON 数据
    
    支持多种格式：
    1. 纯 JSON 对象
    2. 代码块中的 JSON (```json ... ```)
    3. 文本中的 JSON 对象
    
    Args:
        text: LLM 返回的文本
    
    Returns:
        解析出的 JSON 对象，如果解析失败返回 None
    """
    if not text:
        return None
    
    # 尝试提取代码块中的 JSON
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试直接查找 JSON 对象（更精确的匹配）
    # 查找最外层的 JSON 对象
    brace_count = 0
    start_idx = -1
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                try:
                    json_str = text[start_idx:i+1]
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    start_idx = -1
                    continue
    
    return None


def parse_chart_data(text: str) -> Optional[dict]:
    """
    从文本中解析图表数据
    
    Args:
        text: 包含 <<<CHART_DATA>>> 标记的文本
    
    Returns:
        解析出的 JSON 数据，如果未找到则返回 None
    """
    pattern = r'<<<CHART_DATA>>>\s*(\{.*?\})\s*<<<CHART_DATA>>>'
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


async def stream_fortune_analysis(request: FortuneRequest):
    """
    流式返回命理分析结果
    
    Args:
        request: 命理分析请求
    
    Yields:
        流式文本数据
    """
    if not compass_client:
        yield "data: " + json.dumps({
            "error": "Compass API 未配置，请在 .env 文件中设置 COMPASS_API_KEY"
        }, ensure_ascii=False) + "\n\n"
        return
    
    try:
        # 1. 生成完整的 BaziReport
        bazi_report = calculator.generate_bazi_report(
            birth_date=request.birth_date,
            birth_time=request.birth_time,
            lng=request.lng,
            lat=request.lat,
            gender=request.gender
        )
        
        # 2. 构建系统提示词（传入 BaziReport）
        system_prompt = build_system_prompt(
            bazi_report,
            request.name,
            request.gender,
            request.city
        )
        
        # 3. 构建完整提示词
        full_prompt = f"{system_prompt}\n\n请为 {request.name} 进行详细的命理分析。"
        
        # 4. 调用 Compass API（流式）
        stream = compass_client.models.generate_content_stream(
            model="gemini-2.5-flash",  # 使用 Gemini 2.5 Flash 模型
            contents=full_prompt
        )
        
        full_text = ""
        chart_data_found = False
        
        # 5. 流式返回结果
        for chunk in stream:
            if hasattr(chunk, 'text') and chunk.text:
                content = chunk.text
                full_text += content
                
                # 检查是否包含图表数据
                if not chart_data_found and "<<<CHART_DATA>>>" in full_text:
                    chart_data = parse_chart_data(full_text)
                    if chart_data:
                        chart_data_found = True
                        # 单独发送图表数据
                        yield "data: " + json.dumps({
                            "type": "chart_data",
                            "data": chart_data
                        }, ensure_ascii=False) + "\n\n"
                
                # 发送文本内容
                yield "data: " + json.dumps({
                    "type": "text",
                    "content": content
                }, ensure_ascii=False) + "\n\n"
        
        # 如果流式输出结束时仍未找到图表数据，尝试从完整文本中提取
        if not chart_data_found:
            chart_data = parse_chart_data(full_text)
            if chart_data:
                yield "data: " + json.dumps({
                    "type": "chart_data",
                    "data": chart_data
                }, ensure_ascii=False) + "\n\n"
        
        # 发送计算好的 BaziReport 数据
        yield "data: " + json.dumps({
            "type": "bazi_report",
            "data": bazi_report
        }, ensure_ascii=False) + "\n\n"
        
        # 结束标记
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        yield "data: " + json.dumps({
            "error": str(e)
        }, ensure_ascii=False) + "\n\n"


def parse_llm_json_response(text: str) -> Optional[dict]:
    """
    解析 LLM 返回的 JSON 数据
    
    支持多种格式：
    1. 纯 JSON 对象
    2. 代码块中的 JSON (```json ... ```)
    3. 文本中的 JSON 对象
    
    Args:
        text: LLM 返回的文本
    
    Returns:
        解析出的 JSON 对象，如果解析失败返回 None
    """
    if not text:
        return None
    
    # 尝试提取代码块中的 JSON
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试直接查找 JSON 对象
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    return None


async def call_llm_for_structured_data(bazi_report: dict, name: str, gender: str, city: str, birth_date: str, birth_time: str) -> dict:
    """
    调用 LLM API 获取结构化的命理分析数据
    
    Args:
        bazi_report: 后端计算的排盘数据
        name: 姓名
        gender: 性别
        city: 城市
        birth_date: 出生日期 (YYYY-MM-DD)
        birth_time: 出生时间 (HH:MM)
    
    Returns:
        LLM 返回的结构化数据，如果失败返回空字典
    """
    if not compass_client:
        print("⚠️  compass_client 未初始化，跳过 LLM 调用")
        return {}
    
    try:
        # 提取关键数据
        chart = bazi_report['chart']
        gods = bazi_report.get('gods', {})
        five_elements = bazi_report.get('five_elements_legacy', bazi_report.get('five_elements', {}))
        
        day_master = bazi_report.get('day_master', chart.get('day_gan', ''))
        day_wuxing = gods.get('day_wuxing', '')
        
        # 获取五行百分比
        if isinstance(five_elements, list):
            wuxing_percentages = {elem['name']: elem['percent'] for elem in five_elements}
        else:
            wuxing_percentages = five_elements.get('percentages', {})
        
        # 获取十神列表
        ten_gods_list = []
        if chart.get('shi_shen'):
            shi_shen_dict = chart['shi_shen']
            for key in ['year_shi_shen', 'month_shi_shen', 'hour_shi_shen']:
                shi_shen = shi_shen_dict.get(key, '')
                if shi_shen and shi_shen != '日主' and shi_shen not in ten_gods_list:
                    ten_gods_list.append(shi_shen)
        
        # 解析出生日期和时间
        birth_year = birth_date.split('-')[0] if '-' in birth_date else ''
        birth_month = birth_date.split('-')[1] if '-' in birth_date else ''
        birth_day = birth_date.split('-')[2] if '-' in birth_date else ''
        birth_hour = birth_time.split(':')[0] if ':' in birth_time else ''
        birth_minute = birth_time.split(':')[1] if ':' in birth_time else ''
        
        # 构建 System Prompt
        system_prompt = f"""你是一位精通八字与紫微斗数的传统文化研究者。请根据用户的【生辰八字、性别、出生地】进行深度推演。

【用户信息】
姓名：{name}
性别：{gender}
出生日期：{birth_date}（{birth_year}年{birth_month}月{birth_day}日）
出生时间：{birth_time}（{birth_hour}时{birth_minute}分）
出生地：{city}

【排盘数据】
日主：{day_master}（{day_wuxing}）
四柱：{chart.get('si_zhu', {}).get('year', '')} {chart.get('si_zhu', {}).get('month', '')} {chart.get('si_zhu', {}).get('day', '')} {chart.get('si_zhu', {}).get('hour', '')}
五行能量：木({wuxing_percentages.get('木', 0)}%), 火({wuxing_percentages.get('火', 0)}%), 土({wuxing_percentages.get('土', 0)}%), 金({wuxing_percentages.get('金', 0)}%), 水({wuxing_percentages.get('水', 0)}%)
十神配置：{', '.join(ten_gods_list) if ten_gods_list else '无'}

【重要要求】
1. **命理精华（summary）要求**：
   - 请结合日元属性（{day_master}，{day_wuxing}）与十神分布（{', '.join(ten_gods_list) if ten_gods_list else '无'}）进行个性化分析
   - 不要使用通用的套话，必须针对此人的具体命局特点进行描述
   - 字数不少于100字，具有专业感且带有温度
   - 描述要准确反映五行能量分布（木{wuxing_percentages.get('木', 0)}%、火{wuxing_percentages.get('火', 0)}%、土{wuxing_percentages.get('土', 0)}%、金{wuxing_percentages.get('金', 0)}%、水{wuxing_percentages.get('水', 0)}%）的特点
   - 确保文本描述与五行能量数据在逻辑上完全一致

2. **JSON 格式要求**：
   必须返回一个有效的 JSON 对象，格式如下：
   {{
     "day_master": {{
       "name": "{day_master}",
       "element": "{day_wuxing}"
     }},
     "ten_gods": {json.dumps(ten_gods_list, ensure_ascii=False)},
     "personality_tags": ["性格关键词1", "性格关键词2", "性格关键词3"],
     "summary": "命理精华文本（不少于100字，个性化、专业、有温度）",
     "five_elements": {{
       "木": {wuxing_percentages.get('木', 0)},
       "火": {wuxing_percentages.get('火', 0)},
       "土": {wuxing_percentages.get('土', 0)},
       "金": {wuxing_percentages.get('金', 0)},
       "水": {wuxing_percentages.get('水', 0)}
     }}
   }}

3. **其他要求**：
   - personality_tags 应包含3-5个性格关键词，基于日主{day_master}（{day_wuxing}）和十神配置的特点
   - ten_gods 应包含四柱中出现的十神（排除"日主"）
   - five_elements 的数值必须与上述五行能量百分比完全一致
"""

        # 调用 LLM API（非流式，强制 JSON 格式）
        try:
            # 尝试使用 response_mime_type 参数强制 JSON 输出
            # Gemini API 支持 response_mime_type 参数来强制 JSON 格式
            try:
                # 方法1：使用 config 参数（某些 SDK 版本）
                response = compass_client.models.generate_content(
                    model="gemini-2.5-flash",  # 使用 Gemini 2.5 Flash 模型
                    contents=system_prompt,
                    config={
                        "response_mime_type": "application/json"
                    }
                )
                print("✅ 使用 config 参数设置 JSON 格式（Gemini 2.5）", flush=True)
            except (TypeError, AttributeError) as e1:
                # 方法2：直接使用 response_mime_type 参数（某些 SDK 版本）
                try:
                    response = compass_client.models.generate_content(
                        model="gemini-2.5-flash",  # 使用 Gemini 2.5 Flash 模型
                        contents=system_prompt,
                        response_mime_type="application/json"
                    )
                    print("✅ 使用 response_mime_type 参数设置 JSON 格式（Gemini 2.5）", flush=True)
                except (TypeError, AttributeError) as e2:
                    # 方法3：如果都不支持，使用默认方式，但会在 prompt 中强调 JSON 格式
                    print(f"⚠️  JSON 格式参数不支持，使用默认方式（已在 prompt 中强调 JSON，Gemini 2.5）", flush=True)
                    response = compass_client.models.generate_content(
                        model="gemini-2.5-flash",  # 使用 Gemini 2.5 Flash 模型
                        contents=system_prompt
                    )
        except Exception as e:
            print(f"LLM API 调用异常: {e}")
            return {}
        
        # 获取返回文本
        llm_text = ""
        try:
            # 根据测试，response 有 candidates 属性
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content'):
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'text'):
                                llm_text += part.text
                    elif hasattr(candidate.content, 'text'):
                        llm_text = candidate.content.text
                elif hasattr(candidate, 'text'):
                    llm_text = candidate.text
            elif hasattr(response, 'text'):
                llm_text = response.text
            elif hasattr(response, 'content'):
                if hasattr(response.content, 'parts'):
                    for part in response.content.parts:
                        if hasattr(part, 'text'):
                            llm_text += part.text
                elif hasattr(response.content, 'text'):
                    llm_text = response.content.text
        except Exception as e:
            import traceback
            print(f"解析 LLM 响应结构错误: {e}")
            print(traceback.format_exc())
            print(f"Response 类型: {type(response)}")
            print(f"Response 属性: {[attr for attr in dir(response) if not attr.startswith('_')][:15]}")
            llm_text = ""
        
        # 解析 JSON
        if llm_text:
            print(f"LLM 返回文本长度: {len(llm_text)}")
            print(f"LLM 返回文本预览: {llm_text[:300]}")
            parsed_data = parse_llm_json_response(llm_text)
            if parsed_data:
                print(f"✅ 成功解析 LLM JSON，包含字段: {list(parsed_data.keys())}")
                return parsed_data
            else:
                print(f"⚠️  无法解析 LLM 返回的文本为 JSON")
        else:
            print(f"⚠️  LLM 未返回文本内容")
        
        return {}
    except Exception as e:
        print(f"LLM API 调用错误: {e}")
        return {}


@app.post("/api/calculate")
async def calculate_bazi(request: FortuneRequest):
    """
    八字排盘计算接口（升级版：集成 LLM 动态推理）
    
    接收用户信息，返回八字排盘计算结果
    1. 后端计算排盘数据（硬核判定）
    2. 调用 LLM 获取结构化的命理分析数据
    3. 合并数据返回给前端
    """
    try:
        # 1. 生成完整的 BaziReport（后端硬核判定）
        bazi_report = calculator.generate_bazi_report(
            birth_date=request.birth_date,
            birth_time=request.birth_time,
            lng=request.lng,
            lat=request.lat,
            gender=request.gender
        )
        
        # 2. 调用 LLM 获取结构化的命理分析数据
        llm_data = await call_llm_for_structured_data(
            bazi_report,
            request.name,
            request.gender,
            request.city,
            request.birth_date,
            request.birth_time
        )
        
        # 3. 合并 LLM 数据和后端数据
        # 优先使用 LLM 返回的数据，如果没有则使用后端计算的数据
        
        # day_master 数据
        if llm_data.get('day_master'):
            bazi_report['day_master_info'] = llm_data['day_master']
        else:
            gods = bazi_report.get('gods', {})
            day_master = bazi_report.get('day_master', gods.get('day_gan', ''))
            day_wuxing = gods.get('day_wuxing', '')
            if day_master and day_wuxing:
                bazi_report['day_master_info'] = {
                    "name": day_master,
                    "element": day_wuxing
                }
        
        # ten_gods 数据
        if llm_data.get('ten_gods') and len(llm_data.get('ten_gods', [])) > 0:
            bazi_report['ten_gods'] = llm_data['ten_gods']
            print(f"✅ 使用 LLM 的 ten_gods: {llm_data['ten_gods']}", flush=True)
        else:
            # 从后端数据中提取十神
            chart = bazi_report.get('chart', {})
            ten_gods_list = []
            if chart.get('shi_shen'):
                shi_shen_dict = chart['shi_shen']
                for key in ['year_shi_shen', 'month_shi_shen', 'hour_shi_shen']:
                    shi_shen = shi_shen_dict.get(key, '')
                    if shi_shen and shi_shen != '日主' and shi_shen not in ten_gods_list:
                        ten_gods_list.append(shi_shen)
            bazi_report['ten_gods'] = ten_gods_list
            print(f"⚠️  使用后端计算的 ten_gods: {ten_gods_list}", flush=True)
        
        # personality_tags 数据
        if llm_data.get('personality_tags') and len(llm_data.get('personality_tags', [])) > 0:
            bazi_report['personality_tags'] = llm_data['personality_tags']
            # 同时更新 gods 中的 personality_tags（向后兼容）
            if 'gods' in bazi_report:
                bazi_report['gods']['personality_tags'] = llm_data['personality_tags']
            print(f"✅ 使用 LLM 的 personality_tags: {llm_data['personality_tags']}", flush=True)
        else:
            # 使用后端计算的 personality_tags
            gods = bazi_report.get('gods', {})
            personality_tags = gods.get('personality_tags', [])
            bazi_report['personality_tags'] = personality_tags
            print(f"⚠️  使用后端计算的 personality_tags: {personality_tags}", flush=True)
        
        # summary 数据（命理精华）
        if llm_data.get('summary') and len(llm_data.get('summary', '')) > 10:
            bazi_report['essence_text'] = llm_data['summary']
            print(f"✅ 使用 LLM 的 summary: {llm_data['summary'][:50]}...", flush=True)
        else:
            # 使用后端生成的 essence_text
            gods = bazi_report.get('gods', {})
            day_master = bazi_report.get('day_master', gods.get('day_gan', ''))
            day_wuxing = gods.get('day_wuxing', '')
            strength_status = gods.get('strength_status', '')
            pattern_name = gods.get('pattern_name', '')
            personality_tags = gods.get('personality_tags', [])
            
            essence_parts = []
            if day_master and day_wuxing:
                essence_parts.append(f"日主{day_master}，五行属{day_wuxing}")
            if strength_status:
                essence_parts.append(f"日主{strength_status}")
            if pattern_name:
                essence_parts.append(f"格局为{pattern_name}")
            if personality_tags:
                tags_desc = '、'.join(personality_tags[:3])
                essence_parts.append(f"性格{tags_desc}")
            
            essence_text = '，'.join(essence_parts) + '。' if essence_parts else ''
            bazi_report['essence_text'] = essence_text
        
        # five_elements 数据（如果 LLM 返回了，可以用于验证，但优先使用后端计算的）
        # 后端计算的 five_elements 已经包含在 bazi_report 中，不需要覆盖
        
        # 4. 如果启用了自动保存，将结果保存到数据库
        saved_book_id = None
        if request.auto_save:
            if not request.book_name:
                raise HTTPException(
                    status_code=400,
                    detail="当 auto_save=True 时，必须提供 book_name（命书名）"
                )
            
            try:
                # 使用依赖注入获取数据库会话
                db_gen = get_db()
                db = next(db_gen)
                try:
                    # 从 JWT token 或环境变量获取用户ID
                    # 注意：这里需要传入 authorization header，但 calculate_bazi 接口没有接收
                    # 为了保持向后兼容，暂时使用环境变量或默认值
                    current_user_id = get_current_user_id(user_id=None)
                    
                    # 构建完整的summary（包含bazi_report和llm_data）
                    summary_data = {
                        "bazi_report": bazi_report,
                        "llm_data": llm_data,
                        "generated_at": datetime.utcnow().isoformat()
                    }
                    
                    # 创建命书记录
                    fortune_book = FortuneBook(
                        user_id=current_user_id,
                        name=request.book_name,
                        person_name=request.name,
                        birth_date=request.birth_date,
                        birth_time=request.birth_time,
                        gender=request.gender,
                        lat=request.lat,
                        lng=request.lng,
                        city=request.city,
                        summary=json.dumps(summary_data, ensure_ascii=False)  # 存储大模型生成的JSON内容全文
                    )
                    
                    # 持久化到数据库
                    db.add(fortune_book)
                    db.commit()
                    db.refresh(fortune_book)
                    saved_book_id = fortune_book.id
                    print(f"✅ 自动保存命书成功，ID: {saved_book_id}", flush=True)
                except Exception as save_error:
                    db.rollback()
                    print(f"⚠️  自动保存命书失败: {save_error}", flush=True)
                    # 保存失败不影响返回结果，只记录日志
                finally:
                    # 关闭数据库会话
                    try:
                        next(db_gen, None)
                    except StopIteration:
                        pass
            except Exception as db_error:
                print(f"⚠️  获取数据库会话失败: {db_error}", flush=True)
                # 数据库连接失败不影响返回结果
        
        return {
            "success": True,
            "data": bazi_report,
            "saved_book_id": saved_book_id  # 如果自动保存成功，返回book_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/fortune")
async def fortune_analysis(request: FortuneRequest):
    """
    命理分析接口
    
    接收用户信息，返回流式命理分析结果
    """
    return StreamingResponse(
        stream_fortune_analysis(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "命理分析 API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/calculate": "八字排盘计算接口",
            "POST /api/fortune": "命理分析接口",
            "GET /api/user/fortune-books": "获取用户命书列表",
            "POST /api/generate-kline": "生成人生K线数据"
        }
    }


@app.get("/api/user/fortune-books")
@app.get("/api/my-fortune-books")  # 兼容前端使用的路径
async def get_fortune_books(
    user_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    获取用户命书列表
    
    鉴权：从Header中的Authorization token获取user_id，如果没有则使用默认值
    过滤查询：SELECT * FROM fortune_books WHERE user_id = {current_user_id}
    排序：按照创建时间倒序排列 (order_by='created_at desc')
    
    返回字段：
    - id: 命书ID
    - name: 命书名
    - person_name: 姓名
    - birth_details: 简要出生信息（用于前端展示）
    """
    try:
        # 从 JWT token 或 query 参数获取用户ID
        current_user_id = get_current_user_id(authorization=authorization, user_id=user_id)
        
        # 过滤查询：按user_id过滤，按创建时间倒序排列
        books = db.query(FortuneBook).filter(
            FortuneBook.user_id == current_user_id
        ).order_by(FortuneBook.created_at.desc()).all()
        
        return {
            "success": True,
            "data": [book.to_dict() for book in books]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取命书列表失败: {str(e)}")


@app.get("/api/fortune-books/{book_id}")
async def get_fortune_book_by_id(
    book_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    根据ID获取命书详情
    
    路由：GET /api/fortune-books/{book_id}
    用于 Result.jsx 页面加载命书数据
    返回的数据格式必须与大模型实时生成的格式完全一致，否则 Result.jsx 的 UI 组件（如气泡图、五行条）会报错或不显示
    
    关键点：
    1. 从数据库查询 analysis_result 字段
    2. 返回的 summary.bazi_report 格式必须与 /api/calculate 返回的格式完全一致
    3. 必须包含：chart, five_elements, gods, da_yun, true_solar_time 等字段
    """
    try:
        print(f"📖 [GET /api/fortune-books/{book_id}] 请求获取命书详情，ID: {book_id}", flush=True)
        
        # 查询命书
        fortune_book = db.query(FortuneBook).filter(FortuneBook.id == book_id).first()
        
        if not fortune_book:
            print(f"❌ 命书不存在，ID: {book_id}", flush=True)
            raise HTTPException(status_code=404, detail=f"命书不存在：未找到ID为 {book_id} 的命书")
        
        print(f"✅ 找到命书，ID: {book_id}, name: {fortune_book.name}", flush=True)
        
        # 用户权限检查：确保用户只能访问自己的命书
        current_user_id = get_current_user_id(authorization=authorization, user_id=user_id)
        if fortune_book.user_id != current_user_id:
            print(f"❌ 权限拒绝：用户 {current_user_id} 尝试访问用户 {fortune_book.user_id} 的命书", flush=True)
            raise HTTPException(
                status_code=403,
                detail=f"无权访问：该命书不属于当前用户"
            )
        print(f"✅ 权限验证通过：用户 {current_user_id} 访问自己的命书", flush=True)
        
        # 解析 summary 数据（包含完整的 bazi_report）
        summary_data = {}
        if fortune_book.summary:
            try:
                summary_data = json.loads(fortune_book.summary) if isinstance(fortune_book.summary, str) else fortune_book.summary
                print(f"✅ 解析 summary 成功，包含字段: {list(summary_data.keys())}", flush=True)
                
                # 验证 bazi_report 格式
                if summary_data.get('bazi_report'):
                    bazi_report = summary_data['bazi_report']
                    required_fields = ['chart', 'five_elements', 'gods', 'da_yun']
                    missing_fields = [f for f in required_fields if f not in bazi_report]
                    if missing_fields:
                        print(f"⚠️  bazi_report 缺少字段: {missing_fields}", flush=True)
                    else:
                        print(f"✅ bazi_report 格式完整，包含所有必需字段", flush=True)
                else:
                    print(f"⚠️  summary 中没有 bazi_report 字段", flush=True)
            except Exception as e:
                print(f"⚠️  解析 summary 失败: {e}", flush=True)
                import traceback
                print(traceback.format_exc(), flush=True)
        
        # 解析 analysis_result 数据（排盘数据，用于备用）
        analysis_result_data = {}
        if fortune_book.analysis_result:
            try:
                analysis_result_data = json.loads(fortune_book.analysis_result) if isinstance(fortune_book.analysis_result, str) else fortune_book.analysis_result
                print(f"✅ 解析 analysis_result 成功，包含字段: {list(analysis_result_data.keys())}", flush=True)
            except Exception as e:
                print(f"⚠️  解析 analysis_result 失败: {e}", flush=True)
        
        # 构建返回数据
        # Result.jsx 期望从 summary.bazi_report 获取数据，格式必须与 /api/calculate 返回的一致
        book_dict = fortune_book.to_dict_with_id()
        
        # 返回 summary（包含 bazi_report 和 llm_data）
        # 格式必须与实时生成的一致：{ bazi_report: {...}, llm_data: {...} }
        book_dict['summary'] = fortune_book.summary  # 原始 JSON 字符串，前端会解析
        
        # 同时返回 analysis_result（如果需要）
        book_dict['analysis_result'] = fortune_book.analysis_result
        
        print(f"✅ 返回数据准备完成，summary 长度: {len(fortune_book.summary) if fortune_book.summary else 0}", flush=True)
        
        return {
            "success": True,
            "data": book_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ 获取命书详情失败: {str(e)}", flush=True)
        print(traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"获取命书详情失败: {str(e)}")


@app.delete("/api/fortune-books/{book_id}")
async def delete_fortune_book(
    book_id: int,
    authorization: Optional[str] = Header(None),
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    删除命书
    
    路由：DELETE /api/fortune-books/{book_id}
    用于删除用户自己的命书记录
    """
    try:
        print(f"🗑️  [DELETE /api/fortune-books/{book_id}] 请求删除命书，ID: {book_id}", flush=True)
        
        # 查询命书
        fortune_book = db.query(FortuneBook).filter(FortuneBook.id == book_id).first()
        
        if not fortune_book:
            print(f"❌ 命书不存在，ID: {book_id}", flush=True)
            raise HTTPException(status_code=404, detail=f"命书不存在：未找到ID为 {book_id} 的命书")
        
        # 用户权限检查：确保用户只能删除自己的命书
        current_user_id = get_current_user_id(authorization=authorization, user_id=user_id)
        if fortune_book.user_id != current_user_id:
            print(f"❌ 权限拒绝：用户 {current_user_id} 尝试删除用户 {fortune_book.user_id} 的命书", flush=True)
            raise HTTPException(
                status_code=403,
                detail=f"无权删除：该命书不属于当前用户"
            )
        
        print(f"✅ 权限验证通过：用户 {current_user_id} 删除自己的命书", flush=True)
        
        # 删除命书
        db.delete(fortune_book)
        db.commit()
        
        print(f"✅ 命书删除成功，ID: {book_id}", flush=True)
        
        return {
            "success": True,
            "message": f"命书 {book_id} 已成功删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        print(f"❌ 删除命书失败: {str(e)}", flush=True)
        print(traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"删除命书失败: {str(e)}")


@app.post("/api/fortune-books")
async def save_fortune_book(
    request: SaveFortuneBookRequest,
    user_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    保存八字命书到数据库
    
    持久化：调用 db.add() 和 db.commit() 保存到数据库
    关联用户：存储时必须包含 user_id 字段（从当前 Session 或 JWT 中获取）
    存储字段：
    - 基本信息：name, person_name, gender, birth_date, birth_time, lat, lng, city
    - analysis_result: 排盘数据JSON（日元、十神、五行、喜用神、建议等）
    - summary: 大模型生成的JSON内容全文（可选）
    
    返回：保存成功后的记录ID和完整信息
    """
    try:
        print(f"📝 收到保存命书请求: name={request.name}, person_name={request.person_name}", flush=True)
        print(f"   analysis_result 类型: {type(request.analysis_result).__name__ if request.analysis_result else 'None'}", flush=True)
        if isinstance(request.analysis_result, dict):
            print(f"   analysis_result 键: {list(request.analysis_result.keys())}", flush=True)
        
        # 从 JWT token 或 query 参数获取用户ID
        current_user_id = get_current_user_id(authorization=authorization, user_id=user_id)
        
        # 创建命书记录
        fortune_book = FortuneBook(
            user_id=current_user_id,
            name=request.name,
            person_name=request.person_name,
            birth_date=request.birth_date,
            birth_time=request.birth_time,
            gender=request.gender,
            lat=request.lat,
            lng=request.lng,
            city=request.city,
            summary=request.summary,  # 大模型生成的JSON内容全文（可选）
            analysis_result=json.dumps(request.analysis_result, ensure_ascii=False) if request.analysis_result else None  # 排盘数据JSON（将 dict 转换为 JSON 字符串存储）
        )
        
        # 持久化到数据库
        db.add(fortune_book)
        db.commit()
        db.refresh(fortune_book)
        
        saved_id = fortune_book.id
        print(f"✅ 命书保存成功，ID: {saved_id}", flush=True)
        print(f"📋 保存的 new_id (用于前端跳转): {saved_id}", flush=True)  # 打印 new_id 用于调试
        
        # 返回保存的记录ID（字段名必须与前端 CreateForm.jsx 接收的字段名一致）
        # 前端期望: { "id": "生成的ID", "status": "success" }
        return {
            "id": saved_id,  # 必须返回ID（前端使用 savedBook.id）
            "new_id": saved_id,  # 兼容前端使用的 new_id 字段（前端优先使用 savedBook.new_id）
            "status": "success",  # 状态字段（前端期望）
            "success": True,  # 兼容字段
            "data": fortune_book.to_dict_with_id()  # 返回完整信息
        }
    except ValueError as ve:
        # 数据验证错误
        db.rollback()
        print(f"❌ 数据验证错误: {str(ve)}", flush=True)
        raise HTTPException(status_code=400, detail=f"数据验证失败: {str(ve)}")
    except Exception as e:
        db.rollback()
        import traceback
        print(f"❌ 保存命书失败: {str(e)}", flush=True)
        print(traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"保存命书失败: {str(e)}")


@app.post("/api/generate-kline")
async def generate_kline(request: KLineGenerateRequest):
    """
    生成人生K线数据
    
    支持两种入参方式：
    1. 传 book_id：从数据库查询八字信息
    2. 传 birth_data：直接使用表单数据
    
    无论哪种方式，最终都调用相同的 LLM Service 逻辑生成K线数据
    """
    try:
        db = next(get_db())
        
        # 情况1：传了 book_id，从数据库查询
        if request.book_id:
            book = db.query(FortuneBook).filter(FortuneBook.id == request.book_id).first()
            if not book:
                raise HTTPException(status_code=404, detail="命书不存在")
            
            # 从数据库获取数据
            name = book.person_name
            gender = book.gender
            birth_date = book.birth_date
            birth_time = book.birth_time
            lat = book.lat
            lng = book.lng
            city = book.city
        else:
            # 情况2：传了 birth_data，直接使用
            if not all([request.name, request.gender, request.birth_date, 
                       request.birth_time, request.lat is not None, 
                       request.lng is not None, request.city]):
                raise HTTPException(
                    status_code=400, 
                    detail="当未提供 book_id 时，必须提供完整的出生信息（name, gender, birth_date, birth_time, lat, lng, city）"
                )
            
            name = request.name
            gender = request.gender
            birth_date = request.birth_date
            birth_time = request.birth_time
            lat = request.lat
            lng = request.lng
            city = request.city
        
        # 统一的数据结构，传给 Service 层
        # 1. 生成完整的 BaziReport（后端硬核判定）
        bazi_report = calculator.generate_bazi_report(
            birth_date=birth_date,
            birth_time=birth_time,
            lng=lng,
            lat=lat,
            gender=gender
        )
        
        # 2. 调用 LLM 获取结构化的命理分析数据（复用现有逻辑）
        llm_data = await call_llm_for_structured_data(
            bazi_report,
            name,
            gender,
            city,
            birth_date,
            birth_time
        )
        
        # 3. 构建 K 线生成专用的 System Prompt（使用完整的八字数据）
        # 4. 调用 LLM 生成 K 线解读（必须使用真实八字，不能是 Mock）
        if not compass_client:
            raise HTTPException(
                status_code=500,
                detail="Compass API 未配置，无法生成 K 线数据"
            )
        
        # 构建精简的 K 线 Prompt（只要求 JSON 输出，提速）
        # 提取关键八字信息
        chart = bazi_report['chart']
        gods = bazi_report['gods']
        da_yun = bazi_report['da_yun']
        day_master = bazi_report.get('day_master', chart.get('day_gan', ''))
        day_wuxing = gods.get('day_wuxing', '')
        yong_shen = gods.get('useful_gods', [])
        
        # 计算出生年份和当前年龄
        birth_year = datetime.strptime(birth_date, "%Y-%m-%d").year
        current_year = datetime.now().year
        current_age = current_year - birth_year
        
        # 生成 0-100 岁的时间轴（用于计算流年干支和大运）
        # 使用已有的 calculator 实例
        true_solar_time = calculator.calculate_true_solar_time(birth_date, birth_time, lng, lat)
        si_zhu = calculator.get_si_zhu(true_solar_time)
        
        # 计算每个年龄的流年干支和大运
        timeline_data = []
        for age in range(101):  # 0-100岁
            year = birth_year + age
            from lunar_python import Solar
            solar = Solar.fromYmd(year, 1, 1)
            lunar = solar.getLunar()
            year_gan = lunar.getYearGan()
            year_zhi = lunar.getYearZhi()
            liu_nian_gan_zhi = year_gan + year_zhi
            
            # 找到对应的大运
            current_dayun = ''
            for dy in da_yun:
                age_start = dy.get('age_start', 0)
                age_end = dy.get('age_end', 100)
                if age_start <= age < age_end:
                    current_dayun = dy.get('gan_zhi', '')
                    break
            
            timeline_data.append({
                'age': age,
                'year': year,
                'gan_zhi': liu_nian_gan_zhi,
                'da_yun': current_dayun
            })
        
        # 构建精简 Prompt（优化：减少冗余，提高速度）
        kline_prompt = f"""根据八字生成0-100岁K线数据，只返回JSON：

日主: {day_master}（{day_wuxing}）
用神: {', '.join(yong_shen[:3]) if yong_shen else '无'}
大运: {'; '.join([f"{dy.get('age_start', 0)}-{dy.get('age_end', 100)}岁:{dy.get('gan_zhi', '')}" for dy in da_yun[:6]])}

返回格式（纯JSON，无Markdown）：
{{
  "scores": [101个整数，0-100，对应0-100岁],
  "peaks": [{{"age": 13, "score": 85, "reason": "简短原因"}}, ...],
  "valleys": [{{"age": 10, "score": 31, "reason": "简短原因"}}, ...],
  "summary": "100字总结"
}}

要求：scores必须101个，peaks/valleys各3-5个，只返回JSON。
"""
        
        # 调用 LLM API（流式，先传输分析文本，最后传输JSON数据）
        print(f"📊 开始调用 LLM 生成 K 线数据（流式模式）", flush=True)
        
        # 流式返回结果
        async def generate_kline_stream():
            """流式生成K线数据的生成器函数"""
            # 确保 current_age 在函数内部可访问（从外部作用域获取）
            nonlocal current_age
            response_text = ""
            ai_call_success = False
            
            # 首先尝试 Compass API（流式）
            if compass_client:
                try:
                    print("🔄 尝试使用 Compass API（流式）...", flush=True)
                    stream = None
                    try:
                        # 使用流式API
                        stream = compass_client.models.generate_content_stream(
                            model="gemini-2.5-flash",
                            contents=kline_prompt,
                            config={
                                "response_mime_type": "application/json"
                            }
                        )
                        print("✅ 使用流式 API（JSON 模式）", flush=True)
                    except (TypeError, AttributeError) as e1:
                        try:
                            # 回退方案：不使用JSON模式，直接流式
                            stream = compass_client.models.generate_content_stream(
                                model="gemini-2.5-flash",
                                contents=kline_prompt
                            )
                            print("✅ 使用流式 API（默认模式）", flush=True)
                        except Exception as e2:
                            print(f"⚠️  流式 API 调用失败: {e2}", flush=True)
                            stream = None
                
                    # 发送进度：30%（开始调用AI）
                    yield f"data: {json.dumps({'type': 'progress', 'progress': 30}, ensure_ascii=False)}\n\n"
                    
                    # 流式处理响应
                    if stream:
                        try:
                            chunk_count = 0
                            for chunk in stream:
                                chunk_text = ""
                                if hasattr(chunk, 'text'):
                                    chunk_text = chunk.text
                                elif hasattr(chunk, 'candidates') and chunk.candidates:
                                    if hasattr(chunk.candidates[0], 'content'):
                                        if hasattr(chunk.candidates[0].content, 'parts'):
                                            for part in chunk.candidates[0].content.parts:
                                                if hasattr(part, 'text'):
                                                    chunk_text += part.text
                                
                                if chunk_text:
                                    response_text += chunk_text
                                    chunk_count += 1
                                    # 每收到20个chunk，更新一次进度（30% -> 70%）
                                    if chunk_count % 20 == 0:
                                        progress = min(30 + int((chunk_count / 60) * 40), 70)
                                        yield f"data: {json.dumps({'type': 'progress', 'progress': progress}, ensure_ascii=False)}\n\n"
                            
                            if response_text:
                                print(f"✅ Compass API 流式调用成功，返回内容长度: {len(response_text)}", flush=True)
                                ai_call_success = True
                                # 发送进度：70%（AI调用完成）
                                yield f"data: {json.dumps({'type': 'progress', 'progress': 70}, ensure_ascii=False)}\n\n"
                        except Exception as stream_error:
                            print(f"❌ 流式处理错误: {stream_error}", flush=True)
                            stream = None
                    else:
                        print(f"⚠️  流式 API 调用失败，stream 为 None", flush=True)
                        
                except Exception as compass_error:
                    error_msg = str(compass_error)
                    print(f"❌ Compass API 调用失败: {error_msg}", flush=True)
                    
                    # 检查是否是余额不足或其他可恢复错误
                    if "balance" in error_msg.lower() or "402" in error_msg or "quota" in error_msg.lower():
                        print("⚠️  Compass API 余额不足，尝试使用 DeepSeek API 作为备用...", flush=True)
                    else:
                        print("⚠️  Compass API 调用异常，尝试使用 DeepSeek API 作为备用...", flush=True)
            
            # 如果 Compass API 失败，尝试 DeepSeek API（流式）
            if not ai_call_success and deepseek_api_key:
                try:
                    print("🔄 尝试使用 DeepSeek API（流式）...", flush=True)
                    import httpx
                    
                    url = f"{deepseek_base_url}/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {deepseek_api_key}"
                    }
                    
                    payload = {
                        "model": "deepseek-chat",
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一位精通八字命理的大师，擅长根据八字和大运推演人生运势。请严格按照 JSON 格式返回结果，不要包含任何 markdown 标记。"
                            },
                            {
                                "role": "user",
                                "content": kline_prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "response_format": {"type": "json_object"},  # 强制 JSON 输出
                        "stream": True  # 启用流式
                    }
                    
                    # 使用流式调用
                    with httpx.Client(timeout=60.0) as client:
                        with client.stream("POST", url, json=payload, headers=headers) as response:
                            response.raise_for_status()
                            for line in response.iter_lines():
                                if line.startswith("data: "):
                                    data_str = line[6:]  # 移除 "data: " 前缀
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        chunk_data = json.loads(data_str)
                                        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                            delta = chunk_data["choices"][0].get("delta", {})
                                            chunk_text = delta.get("content", "")
                                            if chunk_text:
                                                response_text += chunk_text
                                                # 流式发送文本片段
                                                yield f"data: {json.dumps({'type': 'text', 'content': chunk_text}, ensure_ascii=False)}\n\n"
                                    except json.JSONDecodeError:
                                        continue
                    
                    if response_text:
                        print(f"✅ DeepSeek API 流式调用成功，返回内容长度: {len(response_text)}", flush=True)
                        ai_call_success = True
                        
                except Exception as deepseek_error:
                    print(f"❌ DeepSeek API 调用也失败: {deepseek_error}", flush=True)
                    import traceback
                    print(traceback.format_exc(), flush=True)
            
            # 如果所有 AI 服务都失败，使用默认数据
            if not ai_call_success:
                yield f"data: {json.dumps({'type': 'error', 'content': '所有 AI 服务调用失败，将使用默认数据'}, ensure_ascii=False)}\n\n"
                # 继续处理，使用默认数据
                response_text = "{}"  # 空JSON，将使用默认数据
            
            # 数据清洗：去除 Markdown 标记
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            
            try:
                # 尝试解析 JSON
                try:
                    data = json.loads(clean_json)
                    print("✅ JSON 解析成功", flush=True)
                except json.JSONDecodeError as e:
                    print(f"❌ JSON 解析失败: {e}", flush=True)
                    print(f"❌ 清洗后的内容（前500字符）: {clean_json[:500]}", flush=True)
                    # 如果解析失败，尝试提取 JSON 对象
                    import re
                    json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(0))
                            print("✅ 从文本中提取 JSON 成功", flush=True)
                        except json.JSONDecodeError:
                            data = None
                    else:
                        data = None
                
                # 如果解析失败，使用默认数据
                if not data:
                    raise ValueError("无法解析 JSON，将使用默认数据")
                
                # 提取数据
                scores = data.get("scores", [])
                peaks = data.get("peaks", [])
                valleys = data.get("valleys", [])
                analysis_text = data.get("summary", "基于八字和大运分析，整体运势平稳发展。")
                
                # 验证数组长度（必须是101个）
                if len(scores) != 101:
                    print(f"⚠️  数组长度不正确: scores={len(scores)}，期望101个", flush=True)
                    # 填充或截取到101个
                    if len(scores) < 101:
                        scores.extend([60] * (101 - len(scores)))
                    elif len(scores) > 101:
                        scores[:] = scores[:101]
                
                # 验证高峰和低谷数据
                peaks = [p for p in peaks if isinstance(p, dict) and 'age' in p and 0 <= p['age'] <= 100]
                valleys = [v for v in valleys if isinstance(v, dict) and 'age' in v and 0 <= v['age'] <= 100]
                
                # 生成年份数组和详细信息（0-100岁，共101年）
                chart_points = []
                for i, timeline_point in enumerate(timeline_data):
                    age = timeline_point['age']
                    year = timeline_point['year']
                    gan_zhi = timeline_point['gan_zhi']
                    da_yun = timeline_point['da_yun']
                    score = scores[i] if i < len(scores) else 60
                    
                    # 检查是否是高峰或低谷
                    is_peak = any(p.get('age') == age for p in peaks)
                    is_valley = any(v.get('age') == age for v in valleys)
                    
                    chart_points.append({
                        "age": age,
                        "year": year,
                        "gan_zhi": gan_zhi,
                        "da_yun": da_yun,
                        "score": score,
                        "is_peak": is_peak,
                        "is_valley": is_valley
                    })
                
                # 计算当前运势信息
                current_score = scores[current_age] if current_age < len(scores) else 60
                current_label = "吉" if current_score >= 70 else ("平" if current_score >= 50 else "凶")
                
                # 计算5年趋势（未来5年的平均分 vs 过去5年的平均分）
                future_ages = [current_age + i for i in range(1, 6) if current_age + i < 101]
                past_ages = [current_age - i for i in range(1, 6) if current_age - i >= 0]
                
                future_avg = sum(scores[age] for age in future_ages) / len(future_ages) if future_ages else current_score
                past_avg = sum(scores[age] for age in past_ages) / len(past_ages) if past_ages else current_score
                trend_value = future_avg - past_avg
                trend_direction = "上升" if trend_value > 5 else ("下降" if trend_value < -5 else "平稳")
                
                # 找到下一个高峰和下一个低谷
                next_peak = None
                next_valley = None
                for peak in sorted(peaks, key=lambda x: x.get('age', 0)):
                    if peak.get('age', 0) > current_age:
                        next_peak = peak
                        break
                for valley in sorted(valleys, key=lambda x: x.get('age', 0)):
                    if valley.get('age', 0) > current_age:
                        next_valley = valley
                        break
                
                # 计算人生阶段分析
                stages = [
                    {"name": "童年", "age_range": (0, 12), "scores": scores[0:13]},
                    {"name": "青年", "age_range": (13, 30), "scores": scores[13:31]},
                    {"name": "壮年", "age_range": (31, 50), "scores": scores[31:51]},
                    {"name": "中年", "age_range": (51, 65), "scores": scores[51:66]},
                    {"name": "老年", "age_range": (66, 100), "scores": scores[66:101]}
                ]
                
                stage_analysis = []
                for stage in stages:
                    stage_scores = stage["scores"]
                    if stage_scores:
                        avg_score = sum(stage_scores) / len(stage_scores)
                        stage_analysis.append({
                            "name": stage["name"],
                            "age_range": f"{stage['age_range'][0]}-{stage['age_range'][1]}岁",
                            "avg_score": round(avg_score, 1),
                            "is_current": stage["age_range"][0] <= current_age <= stage["age_range"][1]
                        })
                
                # 获取当前年份的详细信息（需要调用 LLM 生成详细分析）
                current_year_detail = {
                    "age": current_age,
                    "year": chart_points[current_age]["year"] if current_age < len(chart_points) else birth_year + current_age,
                    "gan_zhi": chart_points[current_age]["gan_zhi"] if current_age < len(chart_points) else "",
                    "da_yun": chart_points[current_age]["da_yun"] if current_age < len(chart_points) else "",
                    "score": current_score,
                    "label": current_label,
                    "wealth": "财运稳健，升职加薪",  # 默认值，后续可通过 LLM 生成
                    "interpersonal": "贵人提携",
                    "relationship": "感情正式稳定",
                    "health": "防止过劳",
                    "suitable": "晋升加薪",
                    "avoid": "背后议论"
                }
                
                # 构建返回数据
                chart_data = {
                    "points": chart_points,  # 101个数据点，包含详细信息
                    "peaks": peaks,  # 高峰列表
                    "valleys": valleys,  # 低谷列表
                    "current_age": current_age,  # 当前年龄
                    "current_fortune": {  # 当前运势信息
                        "score": current_score,
                        "label": current_label
                    },
                    "trend_5years": {  # 5年趋势
                        "direction": trend_direction,
                        "value": round(trend_value, 1),
                        "description": f"{trend_direction}" + (f"（{abs(round(trend_value, 1))}分）" if abs(trend_value) > 5 else "")
                    },
                    "next_peak": {  # 下个高峰
                        "age": next_peak.get('age') if next_peak else None,
                        "years_left": next_peak.get('age') - current_age if next_peak else None,
                        "score": next_peak.get('score') if next_peak else None,
                        "reason": next_peak.get('reason') if next_peak else None
                    } if next_peak else None,
                    "next_valley": {  # 需注意时期
                        "age": next_valley.get('age') if next_valley else None,
                        "years_left": next_valley.get('age') - current_age if next_valley else None,
                        "score": next_valley.get('score') if next_valley else None,
                        "reason": next_valley.get('reason') if next_valley else None
                    } if next_valley else None,
                    "stage_analysis": stage_analysis,  # 人生阶段分析
                    "current_year_detail": current_year_detail  # 当前年份详细信息
                }
                
                print(f"✅ K 线数据生成成功: 共{len(chart_points)}个数据点，{len(peaks)}个高峰，{len(valleys)}个低谷", flush=True)
                print(f"✅ 当前运势: {current_score}分 ({current_label}), 5年趋势: {trend_direction}", flush=True)
                
                # 发送进度：95%（数据生成完成）
                yield f"data: {json.dumps({'type': 'progress', 'progress': 95}, ensure_ascii=False)}\n\n"
                
                # 流式发送分析文本
                if analysis_text:
                    yield f"data: {json.dumps({'type': 'analysis', 'content': analysis_text}, ensure_ascii=False)}\n\n"
                
                # 流式发送完整的图表数据
                yield f"data: {json.dumps({'type': 'chart_data', 'data': chart_data}, ensure_ascii=False)}\n\n"
                
                # 发送进度：100%（完成）
                yield f"data: {json.dumps({'type': 'progress', 'progress': 100}, ensure_ascii=False)}\n\n"
                
                # 发送完成标记
                yield f"data: {json.dumps({'type': 'complete', 'data': {'chart_data': chart_data, 'analysis_text': analysis_text, 'bazi_report': bazi_report}}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                print(f"⚠️  LLM API 调用失败: {e}", flush=True)
                import traceback
                print(traceback.format_exc(), flush=True)
                
                # 生成默认数据（兜底）
                print(f"⚠️  使用默认数据（基于大运）", flush=True)
                birth_year = datetime.strptime(birth_date, "%Y-%m-%d").year
                current_year = datetime.now().year
                current_age = current_year - birth_year
            
            da_yun = bazi_report.get('da_yun', [])
            base_score = 60
            
            # 生成 0-100 岁的默认数据
            chart_points = []
            for i, timeline_point in enumerate(timeline_data):
                age = timeline_point['age']
                year = timeline_point['year']
                gan_zhi = timeline_point['gan_zhi']
                da_yun_name = timeline_point['da_yun']
                
                # 根据大运简单调整分数
                score = base_score
                for dy in da_yun:
                    age_start = dy.get('age_start', 0)
                    age_end = dy.get('age_end', 100)
                    if age_start <= age < age_end:
                        score = base_score + 10  # 大运期间分数稍高
                        break
                
                chart_points.append({
                    "age": age,
                    "year": year,
                    "gan_zhi": gan_zhi,
                    "da_yun": da_yun_name,
                    "score": score,
                    "is_peak": False,
                    "is_valley": False
                })
            
            # 计算默认的当前运势信息
            current_score = base_score
            current_label = "平"
            
            # 计算5年趋势
            trend_direction = "平稳"
            trend_value = 0
            
            # 计算人生阶段分析
            stages = [
                {"name": "童年", "age_range": (0, 12), "scores": [base_score] * 13},
                {"name": "青年", "age_range": (13, 30), "scores": [base_score] * 18},
                {"name": "壮年", "age_range": (31, 50), "scores": [base_score] * 20},
                {"name": "中年", "age_range": (51, 65), "scores": [base_score] * 15},
                {"name": "老年", "age_range": (66, 100), "scores": [base_score] * 35}
            ]
            
            stage_analysis = []
            for stage in stages:
                stage_scores = stage["scores"]
                if stage_scores:
                    avg_score = sum(stage_scores) / len(stage_scores)
                    stage_analysis.append({
                        "name": stage["name"],
                        "age_range": f"{stage['age_range'][0]}-{stage['age_range'][1]}岁",
                        "avg_score": round(avg_score, 1),
                        "is_current": stage["age_range"][0] <= current_age <= stage["age_range"][1]
                    })
            
            # 获取当前年份的详细信息
            current_point = chart_points[current_age] if current_age < len(chart_points) else None
            current_year_detail = {
                "age": current_age,
                "year": current_point["year"] if current_point else birth_year + current_age,
                "gan_zhi": current_point["gan_zhi"] if current_point else "",
                "da_yun": current_point["da_yun"] if current_point else "",
                "score": current_score,
                "label": current_label,
                "wealth": "财运一般",
                "interpersonal": "人际关系平稳",
                "relationship": "感情稳定",
                "health": "注意健康",
                "suitable": "稳步发展",
                "avoid": "避免冲动"
            }
            
            chart_data = {
                "points": chart_points,
                "peaks": [],
                "valleys": [],
                "current_age": current_age,
                "current_fortune": {
                    "score": current_score,
                    "label": current_label
                },
                "trend_5years": {
                    "direction": trend_direction,
                    "value": trend_value,
                    "description": trend_direction
                },
                "next_peak": None,
                "next_valley": None,
                "stage_analysis": stage_analysis,
                "current_year_detail": current_year_detail
            }
            # 生成更友好的分析文本
            current_stage_name = '中年'
            if stage_analysis:
                for stage in stage_analysis:
                    if stage.get('is_current'):
                        current_stage_name = stage['name']
                        break
            
            trend_advice = '保持现状，稳步发展'
            if trend_direction == '上升':
                trend_advice = '把握机会，积极进取'
            elif trend_direction == '下降':
                trend_advice = '谨慎行事，稳中求进'
            
                stage_text = '\n'.join([f'- {stage["name"]}（{stage["age_range"]}）：平均运势{stage["avg_score"]}分' for stage in stage_analysis])
                
                analysis_text = f"""基于您的八字和大运分析，整体运势呈现平稳发展态势。

**当前运势（{current_age}岁）**：
当前处于{current_stage_name}阶段，运势{current_label}，分数为{current_score}分。

**5年趋势**：
未来5年运势{trend_direction}，建议{trend_advice}。

**人生阶段分析**：
{stage_text}

**建议**：
请根据个人实际情况调整人生规划，在运势较好的年份把握机会，在运势较弱的年份谨慎行事，注意健康和安全。

*注：当前数据基于大运推算，如需更详细的分析，请联系专业命理师。*"""
                
                # 流式发送分析文本
                if analysis_text:
                    yield f"data: {json.dumps({'type': 'analysis', 'content': analysis_text}, ensure_ascii=False)}\n\n"
                
                # 流式发送完整的图表数据
                yield f"data: {json.dumps({'type': 'chart_data', 'data': chart_data}, ensure_ascii=False)}\n\n"
                
                # 发送完成标记
                yield f"data: {json.dumps({'type': 'complete', 'data': {'chart_data': chart_data, 'analysis_text': analysis_text, 'bazi_report': bazi_report}}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
        
        # 返回流式响应
        return StreamingResponse(
            generate_kline_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 生成K线数据失败: {str(e)}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"生成K线数据失败: {str(e)}")


class LifeLineRequest(BaseModel):
    """人生 K 线请求模型"""
    year: int = Field(..., ge=1900, le=2100, description="出生年份")
    month: int = Field(..., ge=1, le=12, description="出生月份")
    day: int = Field(..., ge=1, le=31, description="出生日期")
    hour: int = Field(..., ge=0, le=23, description="出生小时（0-23）")
    minute: Optional[int] = Field(0, ge=0, le=59, description="出生分钟（0-59），默认为0")
    lng: float = Field(..., description="经度")
    lat: float = Field(..., description="纬度")
    gender: str = Field(..., description="性别（male/female 或 男/女）")
    name: Optional[str] = Field("用户", description="姓名，默认为'用户'")
    
    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v):
        """验证性别字段"""
        v_lower = v.lower()
        if v_lower in ['male', 'm', '男']:
            return 'male'
        elif v_lower in ['female', 'f', '女']:
            return 'female'
        else:
            raise ValueError('性别必须是 male/female 或 男/女')
    
    @field_validator('day')
    @classmethod
    def validate_day(cls, v, info):
        """验证日期是否有效"""
        year = info.data.get('year')
        month = info.data.get('month')
        if year and month:
            try:
                datetime(year, month, v)
            except ValueError:
                raise ValueError(f'日期无效: {year}-{month}-{v}')
        return v


class DivinationRequest(BaseModel):
    """起卦请求模型"""
    stage: str = Field(..., description="阶段：greeting（初始接待）、analysis（正式排盘）、dayun（大运推演）")
    user_input: Optional[str] = Field(None, description="用户输入（生辰信息或'起大运'）")
    birth_date: Optional[str] = Field(None, description="出生日期 YYYY-MM-DD（阶段2和3需要）")
    birth_time: Optional[str] = Field(None, description="出生时间 HH:MM（阶段2和3需要）")
    gender: Optional[str] = Field(None, description="性别（阶段2和3需要）")
    lat: Optional[float] = Field(None, description="纬度（阶段2和3需要）")
    lng: Optional[float] = Field(None, description="经度（阶段2和3需要）")
    city: Optional[str] = Field(None, description="出生地（阶段2和3需要）")
    name: Optional[str] = Field("有缘人", description="姓名")
    
    @field_validator('stage')
    @classmethod
    def validate_stage(cls, v):
        """验证阶段字段"""
        if v not in ['greeting', 'analysis', 'dayun']:
            raise ValueError('阶段必须是 greeting、analysis 或 dayun')
        return v


class DivinationRequest(BaseModel):
    """起卦请求模型"""
    stage: str = Field(..., description="阶段：greeting（初始接待）、analysis（正式排盘）、dayun（大运推演）")
    user_input: Optional[str] = Field(None, description="用户输入（生辰信息或'起大运'）")
    birth_date: Optional[str] = Field(None, description="出生日期 YYYY-MM-DD（阶段2和3需要）")
    birth_time: Optional[str] = Field(None, description="出生时间 HH:MM（阶段2和3需要）")
    gender: Optional[str] = Field(None, description="性别（阶段2和3需要）")
    lat: Optional[float] = Field(None, description="纬度（阶段2和3需要）")
    lng: Optional[float] = Field(None, description="经度（阶段2和3需要）")
    city: Optional[str] = Field(None, description="出生地（阶段2和3需要）")
    name: Optional[str] = Field("有缘人", description="姓名")
    
    @field_validator('stage')
    @classmethod
    def validate_stage(cls, v):
        """验证阶段字段"""
        if v not in ['greeting', 'analysis', 'dayun']:
            raise ValueError('阶段必须是 greeting、analysis 或 dayun')
        return v


@app.post("/api/divination/life-line")
async def generate_life_line(request: LifeLineRequest):
    """
    生成人生 K 线数据
    
    接收前端传来的出生信息（年、月、日、时），调用 LifeLineService 生成 0-100 岁的运势曲线。
    
    返回数据格式：
    - user_profile: 用户信息（name, bazi）
    - chart_data: 0-100岁的数据列表（101个数据点）
    - summary: 总结信息（current_score, trend, peaks, valleys, advice）
    
    异常处理：
    - 如果 AI 返回的 JSON 解析失败或数组长度不够，使用默认值（score=60）填充
    - 确保接口永远返回合法的 101 条数据，防止前端白屏
    """
    try:
        # 1. 格式化出生日期和时间
        birth_date = f"{request.year}-{request.month:02d}-{request.day:02d}"
        birth_time = f"{request.hour:02d}:{request.minute:02d}"
        
        # 记录请求数据
        request_data = {
            "name": request.name or "用户",
            "birth_date": birth_date,
            "birth_time": birth_time,
            "year": request.year,
            "month": request.month,
            "day": request.day,
            "hour": request.hour,
            "minute": request.minute,
            "lng": request.lng,
            "lat": request.lat,
            "gender": request.gender
        }
        print(f"📊 收到 K-Line 请求: {json.dumps(request_data, ensure_ascii=False)}", flush=True)
        
        # 2. 调用 LifeLineService 生成数据
        try:
            result = await lifeline_service.generate_life_curve(
                birth_date=birth_date,
                birth_time=birth_time,
                lng=request.lng,
                lat=request.lat,
                gender=request.gender,
                name=request.name or "用户"
            )
            
            # 3. 验证并修复数据
            chart_data = result.chart_data
            
            # 确保有 101 个数据点（0-100岁）
            if len(chart_data) < 101:
                print(f"⚠️  数据点不足 101 个，当前有 {len(chart_data)} 个，使用默认值填充", flush=True)
                # 使用默认值填充缺失的数据点
                from schemas import ChartDataPoint
                default_data = []
                birth_year = request.year
                for age in range(101):
                    if age < len(chart_data):
                        default_data.append(chart_data[age])
                    else:
                        # 创建默认数据点
                        default_data.append(ChartDataPoint(
                            age=age,
                            year=birth_year + age,
                            score=60,  # 默认分数
                            is_peak=False,
                            is_valley=False,
                            gan_zhi="",  # 如果缺失，可以后续计算
                            da_yun="",
                            details="数据缺失，使用默认值",
                            label="平"
                        ))
                chart_data = default_data
            
            # 验证每个数据点的分数是否在有效范围内
            for i, point in enumerate(chart_data):
                if not (0 <= point.score <= 100):
                    print(f"⚠️  数据点 {i} 的分数 {point.score} 超出范围，修正为 60", flush=True)
                    point.score = 60
            
            # 4. 更新 result 对象
            result.chart_data = chart_data
            
            print(f"✅ 人生 K 线生成成功，返回 {len(chart_data)} 个数据点", flush=True)
            
            # 5. 返回数据（转换为字典，包装成前端期望的格式）
            return {
                "success": True,
                "data": result.dict()
            }
            
        except ValueError as ve:
            # 数据验证错误
            print(f"❌ 数据验证错误: {str(ve)}", flush=True)
            raise HTTPException(status_code=400, detail=f"数据验证失败: {str(ve)}")
        
        except Exception as e:
            # AI 调用失败或其他错误，使用默认数据（兜底策略）
            print(f"⚠️  LifeLineService 调用失败: {str(e)}", flush=True)
            import traceback
            print("=" * 60, flush=True)
            print("错误堆栈:", flush=True)
            print(traceback.format_exc(), flush=True)
            print("=" * 60, flush=True)
            
            # 尝试生成时间轴和八字（即使 AI 失败，也要有基本数据）
            try:
                from calculator import FortuneCalculator
                calculator = FortuneCalculator()
                true_solar_time = calculator.calculate_true_solar_time(
                    birth_date, birth_time, request.lng, request.lat
                )
                si_zhu = calculator.get_si_zhu(true_solar_time)
                bazi = [
                    si_zhu['year_gan'] + si_zhu['year_zhi'],
                    si_zhu['month_gan'] + si_zhu['month_zhi'],
                    si_zhu['day_gan'] + si_zhu['day_zhi'],
                    si_zhu['hour_gan'] + si_zhu['hour_zhi']
                ]
            except Exception as calc_error:
                print(f"⚠️  八字计算也失败: {calc_error}", flush=True)
                bazi = []
            
            # 生成默认的 101 个数据点（Mock 数据 - 平稳曲线）
            from schemas import ChartDataPoint, LifeCurveResponse
            default_chart_data = []
            birth_year = request.year
            
            # 生成一个简单的平稳曲线（60-65 分之间轻微波动）
            import random
            random.seed(birth_year)  # 使用出生年份作为种子，确保结果可复现
            
            for age in range(101):
                # 生成一个平稳的分数（60-65 之间）
                base_score = 60
                variation = random.randint(-2, 5)  # 轻微波动
                score = max(55, min(70, base_score + variation))
                
                default_chart_data.append(ChartDataPoint(
                    age=age,
                    year=birth_year + age,
                    score=score,
                    is_peak=False,
                    is_valley=False,
                    gan_zhi="",  # 可以后续计算，但为了简单先留空
                    da_yun="",
                    details="使用默认数据（AI 服务暂时不可用）",
                    label="平"
                ))
            
            # 返回默认响应（兜底数据）
            default_response = LifeCurveResponse(
                user_profile={
                    "name": request.name or "用户",
                    "bazi": bazi
                },
                chart_data=default_chart_data,
                summary={
                    "current_score": 62,
                    "trend": "平稳",
                    "peaks": [],
                    "valleys": [],
                    "advice": "AI 服务暂时不可用，当前显示为默认数据。请稍后重试或联系管理员。"
                }
            )
            
            print(f"✅ 返回兜底数据（Mock），共 {len(default_chart_data)} 个数据点", flush=True)
            return {
                "success": True,
                "data": default_response.dict()
            }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 生成人生 K 线失败: {str(e)}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"生成人生 K 线失败: {str(e)}")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "compass_configured": compass_client is not None
    }


class ChatDivinationRequest(BaseModel):
    """起卦对话请求模型（有状态版本）"""
    messages: List[Dict[str, str]] = Field(..., description="对话历史记录，格式：[{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}, ...]，最后一条必须是用户消息")
    bazi_data: Optional[Dict] = Field(None, description="八字排盘数据（可选，如果前端已通过表单提交）")


@app.post("/api/chat/divination")
async def chat_divination(request: ChatDivinationRequest):
    """
    起卦对话接口（有状态版本）
    
    处理算命逻辑的对话式接口，支持上下文管理。
    
    Args:
        request: 包含 messages（对话历史，包含 role 和 content）和 bazi_data（八字数据）
    
    Returns:
        流式返回 AI 回复
    """
    if not compass_client:
        raise HTTPException(
            status_code=503,
            detail="AI 服务未配置，请在 .env 文件中设置 COMPASS_API_KEY"
        )
    
    try:
        # 1. 解析消息列表
        if not request.messages or len(request.messages) == 0:
            raise HTTPException(status_code=400, detail="messages 不能为空")
        
        # 分离历史消息和最新消息
        history_messages = request.messages[:-1]  # 除最后一条外的所有消息
        latest_message = request.messages[-1]  # 最后一条消息（用户当前输入）
        
        # 判断是否是首次对话（history 为空）
        is_first_message = len(history_messages) == 0
        
        print(f"📨 收到对话请求，历史消息数: {len(history_messages)}, 是否首次: {is_first_message}", flush=True)
        
        # 2. 将前端消息格式转换为 Google GenAI 的 history 格式
        # Google GenAI 的 history 格式：List[Dict] 其中每个 Dict 包含 'role' 和 'parts'
        # role: 'user' 或 'model'
        # parts: List[Dict] 其中每个 Dict 包含 'text'
        genai_history = []
        
        for msg in history_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # 转换 role：前端使用 'assistant'，GenAI 使用 'model'
            genai_role = "model" if role == "assistant" else "user"
            
            genai_history.append({
                "role": genai_role,
                "parts": [{"text": content}]
            })
        
        # 3. 构建 System Prompt（仅在首次对话时注入）
        # 获取当前时间信息（用于所有对话）
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        current_time_obj = datetime.now()
        current_year = current_time_obj.year
        current_month = current_time_obj.month
        current_day = current_time_obj.day
        current_hour = current_time_obj.hour
        current_minute = current_time_obj.minute
        current_datetime_str = f"{current_year}年{current_month}月{current_day}日{current_hour}点{current_minute}分"
        next_year = current_year + 1
        next_year_2 = current_year + 2
        
        system_instruction = None
        if is_first_message:
            # 检测是否是单一事件起卦需求
            latest_content_for_check = latest_message.get('content', '')
            single_event_keywords = [
                "论文", "paper", "投稿", "中稿", "发表", "期刊", "会议", "录用", "审稿",
                "求职", "面试", "offer", "工作", "跳槽", "升职",
                "投资", "股票", "基金", "理财", "赚钱",
                "感情", "恋爱", "分手", "复合", "结婚", "离婚",
                "考试", "考研", "考公", "录取", "通过",
                "能不能", "会不会", "能否", "是否", "成功", "失败"
            ]
            is_single_event = any(keyword in latest_content_for_check for keyword in single_event_keywords)
            
            if is_single_event:
                # 使用单一事件起卦专用 System Prompt，并在第一行注入当前时间
                system_prompt = f"当前系统时间：{current_time} (模型必须以此为准)。\n" + SINGLE_EVENT_DIVINATION_PROMPT
                # 注入当前时间信息
                system_prompt += f"\n\n【重要时间信息】\n当前时间是：{current_datetime_str}（北京时间）。\n当前年份是：{current_year}年。\n所有涉及年份的分析必须基于当前年份（{current_year}年）进行计算，严禁使用过时的年份（如2023、2024、2025等）。\n当用户问'明年'时，指的是{next_year}年；问'后年'时，指的是{next_year_2}年。"
                print(f"📊 首次对话，使用单一事件起卦 System Prompt，当前时间: {current_time}", flush=True)
            else:
                # 使用普通命理咨询 System Prompt，并在第一行注入当前时间
                system_prompt = f"当前系统时间：{current_time} (模型必须以此为准)。\n" + DIVINATION_SYSTEM_PROMPT
                # 注入当前时间信息
                system_prompt += f"\n\n【重要时间信息】\n当前时间是：{current_datetime_str}（北京时间）。\n当前年份是：{current_year}年。\n所有涉及年份的分析必须基于当前年份（{current_year}年）进行计算，严禁使用过时的年份（如2023、2024、2025等）。\n当用户问'明年'时，指的是{next_year}年；问'后年'时，指的是{next_year_2}年。\n未来3年流年预警必须从{current_year}年开始分析（{current_year}年、{next_year}年、{next_year_2}年）。"
                # 如果提供了八字数据，添加到 System Prompt 中
                if request.bazi_data:
                    bazi_json = json.dumps(request.bazi_data, ensure_ascii=False, indent=2)
                    system_prompt += f"\n\n【当前用户的八字排盘数据】\n{bazi_json}\n\n请基于以上八字数据进行精准分析。"
                print(f"📊 首次对话，使用普通命理咨询 System Prompt，当前时间: {current_time}，八字数据: {bool(request.bazi_data)}", flush=True)
            
            system_instruction = system_prompt
        else:
            print(f"📊 后续对话，不注入 System Prompt，历史消息数: {len(history_messages)}", flush=True)
        
        # 4. 检测用户需求类型（单一事件起卦 or 普通命理咨询 or tab点击）
        latest_content = latest_message.get('content', '')
        
        # 检测是否是单一事件起卦需求（已在首次对话时检测过，这里用于后续对话）
        is_single_event_divination = False
        if not is_first_message:
            single_event_keywords = [
                "论文", "paper", "投稿", "中稿", "发表", "期刊", "会议", "录用", "审稿",
                "求职", "面试", "offer", "工作", "跳槽", "升职",
                "投资", "股票", "基金", "理财", "赚钱",
                "感情", "恋爱", "分手", "复合", "结婚", "离婚",
                "考试", "考研", "考公", "录取", "通过",
                "能不能", "会不会", "能否", "是否", "成功", "失败"
            ]
            if any(keyword in latest_content for keyword in single_event_keywords):
                is_single_event_divination = True
                print(f"🔍 检测到单一事件起卦需求（后续对话）", flush=True)
        
        # 兼容旧代码：保留 is_paper_divination 变量
        is_paper_divination = is_single_event_divination
        
        # 检测用户点击的tab类型
        tab_type = None
        if not is_single_event_divination:
            if "起大运" in latest_content or "大运" in latest_content:
                tab_type = "起大运"
            elif "看事业" in latest_content or "事业" in latest_content:
                tab_type = "看事业"
            elif "看姻缘" in latest_content or "姻缘" in latest_content or "婚姻" in latest_content:
                tab_type = "看姻缘"
            elif "看财运" in latest_content or "财运" in latest_content:
                tab_type = "看财运"
            elif "看健康" in latest_content or "健康" in latest_content:
                tab_type = "看健康"
            elif "详细分析" in latest_content:
                tab_type = "详细分析"
        
        # 5. 如果检测到快捷指令或单一事件起卦，追加隐藏的 system instruction（防重复机制）
        additional_instruction = None
        if is_single_event_divination and not is_first_message:
            # 后续对话中的单一事件起卦，追加指令（包含当前时间）
            additional_instruction = f"用户请求单一事件起卦。请使用梅花易数、奇门遁甲和小六壬三种方式进行测算。如果用户已提供完整信息（出生年月日时、问题、当前时间、三个数字），立即进行起卦测算；如果信息不完整，一次性引导用户提供所有信息。\n\n【重要时间信息】当前时间是：{current_datetime_str}（北京时间）。当前年份是：{current_year}年。所有涉及年份的分析必须基于当前年份（{current_year}年）进行计算，严禁使用过时的年份（如2023、2024、2025等）。当用户问'明年'时，指的是{next_year}年；问'后年'时，指的是{next_year_2}年。"
            print(f"🔍 检测到单一事件起卦需求（后续对话），追加起卦指令，当前时间: {current_datetime_str}", flush=True)
        elif tab_type and not is_first_message:
            # 后续对话中的tab点击，追加指令（包含当前时间）
            additional_instruction = f"用户基于已有的排盘信息请求详解【{tab_type}】板块。请勿重复排盘，直接根据上下文输出深度分析（≥300字）。\n\n【重要时间信息】当前时间是：{current_datetime_str}（北京时间）。当前年份是：{current_year}年。所有涉及年份的分析必须基于当前年份（{current_year}年）进行计算，严禁使用过时的年份（如2023、2024、2025等）。当用户问'明年'时，指的是{next_year}年；问'后年'时，指的是{next_year_2}年。"
            print(f"🔍 检测到用户点击tab: {tab_type}，追加防重复指令，当前时间: {current_datetime_str}", flush=True)
        elif not is_first_message:
            # 所有后续对话都注入当前时间信息（确保时间准确性）
            additional_instruction = f"【重要时间信息】当前时间是：{current_datetime_str}（北京时间）。当前年份是：{current_year}年。所有涉及年份的分析必须基于当前年份（{current_year}年）进行计算，严禁使用过时的年份（如2023、2024、2025等）。当用户问'明年'时，指的是{next_year}年；问'后年'时，指的是{next_year_2}年。"
            print(f"📅 后续对话，注入当前时间信息: {current_datetime_str}", flush=True)
        
        # 6. 创建聊天会话（使用 chats.create）
        model_name = "gemini-2.5-flash"  # 使用最快的模型
        latest_content = latest_message.get('content', '')
        
        # 如果检测到快捷指令，将 additional_instruction 添加到当前消息前
        if additional_instruction:
            latest_content = f"{additional_instruction}\n\n用户问题：{latest_content}"
        
        try:
            # 创建聊天会话，传入 history 和 system_instruction
            chat_config = {
                "model": model_name,
                "history": genai_history,
            }
            
            # 仅在首次对话时添加 system_instruction
            if system_instruction:
                chat_config["system_instruction"] = system_instruction
            
            chat = compass_client.chats.create(**chat_config)
            print(f"✅ 创建聊天会话成功，history 长度: {len(genai_history)}", flush=True)
            
            # 使用 chat.send_message() 发送消息并获取流式响应
            stream = chat.send_message(latest_content, stream=True)
            print(f"✅ 发送消息成功: {latest_content[:50]}...", flush=True)
            
        except Exception as e:
            print(f"❌ 创建聊天会话或发送消息失败: {e}", flush=True)
            import traceback
            traceback.print_exc()
            # 如果 chats.create 失败，回退到 generate_content_stream
            print("⚠️  回退到 generate_content_stream 方法", flush=True)
            
            # 构建完整的 prompt（回退方案）
            if is_first_message:
                full_prompt = f"{system_instruction}\n\n用户：{latest_content}"
            else:
                history_text = ""
                for msg in history_messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        history_text += f"用户：{content}\n\n"
                    elif role == "assistant":
                        history_text += f"助手：{content}\n\n"
                full_prompt = f"{history_text}用户：{latest_content}"
            
            try:
                stream = compass_client.models.generate_content_stream(
                    model=model_name,
                    contents=full_prompt
                )
            except Exception as e2:
                print(f"❌ 回退方案也失败: {e2}", flush=True)
                raise HTTPException(status_code=500, detail=f"AI 服务调用失败: {str(e2)}")
            
            # 3. 流式返回结果
            async def generate_response():
                full_text = ""
                try:
                    for chunk in stream:
                        chunk_text = ""
                        if hasattr(chunk, 'text'):
                            chunk_text = chunk.text
                        elif hasattr(chunk, 'candidates') and chunk.candidates:
                            if hasattr(chunk.candidates[0], 'content'):
                                if hasattr(chunk.candidates[0].content, 'parts'):
                                    for part in chunk.candidates[0].content.parts:
                                        if hasattr(part, 'text'):
                                            chunk_text += part.text
                        
                        if chunk_text:
                            full_text += chunk_text
                            yield f"data: {json.dumps({'type': 'text', 'content': chunk_text}, ensure_ascii=False)}\n\n"
                    
                    # 发送完成标记
                    yield "data: [DONE]\n\n"
                    print(f"✅ 起卦对话完成，总长度: {len(full_text)} 字符", flush=True)
                    
                except Exception as e:
                    print(f"❌ 流式输出错误: {e}", flush=True)
                    yield f"data: {json.dumps({'type': 'error', 'content': f'生成错误: {str(e)}'}, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(
                generate_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
            
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
            raise HTTPException(
                status_code=500,
                detail=f"AI 服务调用失败: {str(e)}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 起卦对话接口错误: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        raise HTTPException(
            status_code=500,
            detail=f"起卦对话失败: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


def build_divination_prompt(stage: str, bazi_report: dict, name: str, gender: str, city: str) -> str:
    """
    构建起卦功能的提示词
    
    Args:
        stage: 阶段（analysis 或 dayun）
        bazi_report: 八字排盘数据
        name: 姓名
        gender: 性别
        city: 城市
    
    Returns:
        提示词字符串
    """
    chart = bazi_report.get('chart', {})
    si_zhu = chart.get('si_zhu', {})
    day_master = bazi_report.get('day_master', '')
    gods = bazi_report.get('gods', {})
    five_elements = bazi_report.get('five_elements_legacy', bazi_report.get('five_elements', {}))
    da_yun = bazi_report.get('da_yun', [])
    
    # 格式化大运信息
    dayun_text = ""
    for i, dy in enumerate(da_yun[:4]):  # 只取前4步大运
        age_start = dy.get('age_start', 0)
        age_end = dy.get('age_end', 10)
        gan_zhi = dy.get('gan_zhi', '')
        dayun_text += f"第{i+1}步大运：{age_start}-{age_end}岁，{gan_zhi}\n"
    
    if stage == 'analysis':
        prompt = f"""你是一位精通子平八字、紫微斗数、皇极经世书的"AI 命理先知"。你熟读台湾无居士《拆穿铁板神数》与王亭之的斗数论述，深谙阴阳五行与现代心理学。

你的语言风格：半文半白但通俗易懂，语气权威、客观、带有悲悯之心，像一位隐居的得道高人。

请为 {name}（{gender}，生于{city}）进行命理分析。

【八字排盘】
年柱：{si_zhu.get('year_gan', '')}{si_zhu.get('year_zhi', '')}
月柱：{si_zhu.get('month_gan', '')}{si_zhu.get('month_zhi', '')}
日柱：{si_zhu.get('day_gan', '')}{si_zhu.get('day_zhi', '')}（日主：{day_master}）
时柱：{si_zhu.get('hour_gan', '')}{si_zhu.get('hour_zhi', '')}

【分析要求】
请按照以下格式输出，使用 Markdown 格式，关键结论用 **加粗** 或 > 引用标出：

## 一、八字排盘
列出四柱（年/月/日/时），标明"日主"及五行属性。

## 二、基本面分析
基于月令与日主关系，分析强弱、格局（≥300字）。

## 三、五大板块详解

### 1. 个性
关键词+≥300字深度解析，结合十神心性。

### 2. 事业
适合行业+成就高低，≥300字。

### 3. 财运
正财vs偏财，一生财源，≥300字。

### 4. 婚姻
配偶特征+早晚婚建议，≥300字。

### 5. 健康
五行强弱对应的脏腑隐患，≥300字。

### 6. 未来1年流年趋势
≥300字。

## 结尾引导
分析完上述内容后，**必须停止输出**，并询问用户："如果你愿意，下一步我可以为你精准起大运（每十年），并指出哪一年是你真正的转命点。你只需说一句：『起大运』"。

要求：
- 语言风格：半文半白，通俗易懂，权威客观，带有悲悯之心
- 结合子平法（旺衰、格局、调候）和紫微斗数
- 将古代术语转化为现代职场/情感建议
- 不要一次性输出所有内容，分阶段引导"""
    
    elif stage == 'dayun':
        prompt = f"""你是一位精通子平八字、紫微斗数、皇极经世书的"AI 命理先知"。你熟读台湾无居士《拆穿铁板神数》与王亭之的斗数论述，深谙阴阳五行与现代心理学。

你的语言风格：半文半白但通俗易懂，语气权威、客观、带有悲悯之心，像一位隐居的得道高人。

请为 {name}（{gender}，生于{city}）进行大运推演。

【八字排盘】
年柱：{si_zhu.get('year_gan', '')}{si_zhu.get('year_zhi', '')}
月柱：{si_zhu.get('month_gan', '')}{si_zhu.get('month_zhi', '')}
日柱：{si_zhu.get('day_gan', '')}{si_zhu.get('day_zhi', '')}（日主：{day_master}）
时柱：{si_zhu.get('hour_gan', '')}{si_zhu.get('hour_zhi', '')}

【大运信息】
{dayun_text}

【分析要求】
请按照以下格式输出，使用 Markdown 格式，关键结论用 **加粗** 或 > 引用标出：

## 一、起运原理
解释为何顺/逆行，几岁起运。

## 二、大运流变
按时间轴列出前 3-4 步大运（包括当前大运）。
每一运需包含：大运干支、核心关键词、吉凶断语。
**重点分析【当前大运】**：指出核心机会与风险（≥300字）。

## 三、总结与福报
给出"一生命运总评"和"劫难与福报"分析。

要求：
- 语言风格：半文半白，通俗易懂，权威客观，带有悲悯之心
- 结合子平法（旺衰、格局、调候）和紫微斗数
- 将古代术语转化为现代职场/情感建议"""
    
    else:
        prompt = ""
    
    return prompt


@app.post("/api/divination")
async def divination(request: DivinationRequest):
    """
    起卦功能接口
    
    分三个阶段：
    1. greeting: 初始接待，引导用户提供生辰信息
    2. analysis: 正式排盘，八字排盘+五大板块分析
    3. dayun: 大运推演，当用户输入"起大运"后执行
    """
    try:
        if request.stage == 'greeting':
            # 阶段1：初始接待
            greeting_text = """**AI算命·命理先知**

有缘人，你好。

> 不知生辰，不敢妄断。

在下虽习得子平八字、紫微斗数、皇极经世书，然命理一道，最重精准。若无准确的生辰八字，纵有千般算法，亦如盲人摸象，难窥天机。

**请提供以下信息：**
1. 出生年月日（公历）
2. 时辰（尽量精确，如：上午9点、下午3点30分等）
3. 性别
4. 出生地（城市名称即可）

待你提供完整信息后，我当为你排盘推演，解析命理。"""
            
            return {
                "success": True,
                "stage": "greeting",
                "content": greeting_text,
                "next_stage": "analysis"
            }
        
        elif request.stage == 'analysis':
            # 阶段2：正式排盘
            # 验证必需字段
            if not all([request.birth_date, request.birth_time, request.gender, request.lat, request.lng]):
                raise HTTPException(
                    status_code=400,
                    detail="阶段2（正式排盘）需要提供：birth_date, birth_time, gender, lat, lng"
                )
            
            # 生成八字排盘
            bazi_report = calculator.generate_bazi_report(
                birth_date=request.birth_date,
                birth_time=request.birth_time,
                lng=request.lng,
                lat=request.lat,
                gender=request.gender
            )
            
            # 构建提示词
            prompt = build_divination_prompt(
                stage='analysis',
                bazi_report=bazi_report,
                name=request.name,
                gender=request.gender,
                city=request.city or "未知"
            )
            
            # 调用 LLM 生成分析
            if not compass_client:
                # 如果没有 LLM，返回基础分析
                return {
                    "success": True,
                    "stage": "analysis",
                    "content": "AI 服务未配置，无法生成详细分析。",
                    "bazi_report": bazi_report
                }
            
            try:
                response = compass_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                
                # 获取返回文本
                analysis_text = ""
                if hasattr(response, 'text'):
                    analysis_text = response.text
                elif hasattr(response, 'candidates') and response.candidates:
                    if hasattr(response.candidates[0], 'content'):
                        if hasattr(response.candidates[0].content, 'parts'):
                            for part in response.candidates[0].content.parts:
                                if hasattr(part, 'text'):
                                    analysis_text += part.text
                
                return {
                    "success": True,
                    "stage": "analysis",
                    "content": analysis_text,
                    "bazi_report": bazi_report,
                    "next_stage": "dayun"
                }
            except Exception as e:
                print(f"⚠️  LLM 调用失败: {e}", flush=True)
                # 返回基础分析
                chart = bazi_report.get('chart', {})
                si_zhu = chart.get('si_zhu', {})
                day_master = bazi_report.get('day_master', '')
                
                basic_analysis = f"""## 一、八字排盘

**年柱**：{si_zhu.get('year_gan', '')}{si_zhu.get('year_zhi', '')}
**月柱**：{si_zhu.get('month_gan', '')}{si_zhu.get('month_zhi', '')}
**日柱**：{si_zhu.get('day_gan', '')}{si_zhu.get('day_zhi', '')}（**日主：{day_master}**）
**时柱**：{si_zhu.get('hour_gan', '')}{si_zhu.get('hour_zhi', '')}

> AI 服务暂时不可用，当前显示为基础排盘信息。如需详细分析，请稍后重试。"""
                
                return {
                    "success": True,
                    "stage": "analysis",
                    "content": basic_analysis,
                    "bazi_report": bazi_report,
                    "next_stage": "dayun"
                }
        
        elif request.stage == 'dayun':
            # 阶段3：大运推演
            # 验证必需字段
            if not all([request.birth_date, request.birth_time, request.gender, request.lat, request.lng]):
                raise HTTPException(
                    status_code=400,
                    detail="阶段3（大运推演）需要提供：birth_date, birth_time, gender, lat, lng"
                )
            
            # 生成八字排盘
            bazi_report = calculator.generate_bazi_report(
                birth_date=request.birth_date,
                birth_time=request.birth_time,
                lng=request.lng,
                lat=request.lat,
                gender=request.gender
            )
            
            # 构建提示词
            prompt = build_divination_prompt(
                stage='dayun',
                bazi_report=bazi_report,
                name=request.name,
                gender=request.gender,
                city=request.city or "未知"
            )
            
            # 调用 LLM 生成分析
            if not compass_client:
                return {
                    "success": True,
                    "stage": "dayun",
                    "content": "AI 服务未配置，无法生成大运分析。",
                    "bazi_report": bazi_report
                }
            
            try:
                response = compass_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                
                # 获取返回文本
                analysis_text = ""
                if hasattr(response, 'text'):
                    analysis_text = response.text
                elif hasattr(response, 'candidates') and response.candidates:
                    if hasattr(response.candidates[0], 'content'):
                        if hasattr(response.candidates[0].content, 'parts'):
                            for part in response.candidates[0].content.parts:
                                if hasattr(part, 'text'):
                                    analysis_text += part.text
                
                return {
                    "success": True,
                    "stage": "dayun",
                    "content": analysis_text,
                    "bazi_report": bazi_report
                }
            except Exception as e:
                print(f"⚠️  LLM 调用失败: {e}", flush=True)
                # 返回基础大运信息
                da_yun = bazi_report.get('da_yun', [])
                dayun_text = "\n".join([
                    f"第{i+1}步大运：{dy.get('age_start', 0)}-{dy.get('age_end', 10)}岁，{dy.get('gan_zhi', '')}"
                    for i, dy in enumerate(da_yun[:4])
                ])
                
                basic_dayun = f"""## 一、起运原理

根据你的八字，大运按{'顺' if request.gender == 'male' else '逆'}行推算。

## 二、大运流变

{dayun_text}

> AI 服务暂时不可用，当前显示为基础大运信息。如需详细分析，请稍后重试。"""
                
                return {
                    "success": True,
                    "stage": "dayun",
                    "content": basic_dayun,
                    "bazi_report": bazi_report
                }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 起卦功能错误: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        raise HTTPException(status_code=500, detail=f"起卦功能失败: {str(e)}")


class ChatDivinationRequest(BaseModel):
    """起卦对话请求模型（有状态版本）"""
    messages: List[Dict[str, str]] = Field(..., description="对话历史记录，格式：[{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}, ...]，最后一条必须是用户消息")
    bazi_data: Optional[Dict] = Field(None, description="八字排盘数据（可选，如果前端已通过表单提交）")


@app.post("/api/chat/divination")
async def chat_divination(request: ChatDivinationRequest):
    """
    起卦对话接口
    
    处理算命逻辑的对话式接口，支持上下文管理。
    
    Args:
        request: 包含 messages（对话历史）和 user_id（用户ID）
    
    Returns:
        流式返回 AI 回复
    """
    if not compass_client:
        raise HTTPException(
            status_code=503,
            detail="AI 服务未配置，请在 .env 文件中设置 COMPASS_API_KEY"
        )
    
    try:
        # 1. 构建消息列表
        messages = []
        
        # 1.1 添加 System Prompt
        system_prompt = DIVINATION_SYSTEM_PROMPT
        
        # 1.2 八字数据将在构建 prompt 时单独添加，确保模型能清楚看到
        # 这里先记录，稍后在 conversation_parts 中添加
        
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 1.3 添加历史对话记录（前端传来的 messages）
        # 过滤掉可能的 system 消息，避免重复
        user_inputs = []
        assistant_responses = []
        
        for msg in request.messages:
            if isinstance(msg, dict) and msg.get("role") != "system":
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "user":
                    user_inputs.append(content)
                elif role == "assistant":
                    assistant_responses.append(content)
                
                messages.append({
                    "role": role,
                    "content": content
                })
        
        # 1.4 状态判定：检测用户是否输入"起大运"
        # 检查最后一条用户消息是否包含"起大运"
        last_user_input = user_inputs[-1] if user_inputs else ""
        is_dayun_request = "起大运" in last_user_input or "大运" in last_user_input
        
        if is_dayun_request:
            # 如果用户要求起大运，添加系统指令跳过排盘和板块分析
            dayun_instruction = """【重要指令】
用户已阅读基本分析，现在请跳过【八字排盘】和【基本面分析】板块，直接进入【大运推演】阶段。

请直接开始分析：
1. 起运原理（为何顺/逆行，几岁起运）
2. 大运流变（前3-4步大运，重点分析当前大运）
3. 总结与福报

不要重复输出排盘和基本面分析内容。"""
            
            messages.append({
                "role": "system",
                "content": dayun_instruction
            })
            print(f"🔍 检测到用户要求起大运，已添加跳过指令", flush=True)
        
        print(f"📨 收到起卦对话请求，消息数: {len(messages)}, 是否起大运: {is_dayun_request}, 八字数据: {bool(request.bazi_data)}", flush=True)
        
        # 2. 调用 LLM（流式输出）
        try:
            # 使用 Gemini 2.5 Flash 或 Pro 1.5（支持长文本）
            model_name = "gemini-2.5-flash"  # 或 "gemini-1.5-pro" 如果需要更长上下文
            
            # 转换消息格式为 Gemini API 格式
            # Gemini API 使用 contents 参数，可以是字符串或消息列表
            # 我们需要将对话历史转换为 Gemini 格式
            
            # 提取 system prompt 和额外指令
            system_prompt_content = ""
            additional_instructions = []
            user_messages = []
            assistant_messages = []
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    if content == system_prompt:
                        system_prompt_content = content
                    else:
                        # 这是额外的系统指令（如"起大运"指令）
                        additional_instructions.append(content)
                elif role == "user":
                    user_messages.append(content)
                elif role == "assistant":
                    assistant_messages.append(content)
            
            # 构建完整的 prompt
            # 将 system prompt 和对话历史合并
            conversation_parts = []
            
            # 先添加主要的 system prompt
            if system_prompt_content:
                conversation_parts.append(system_prompt_content)
            
            # 如果有八字数据，明确提示模型使用这些数据
            if request.bazi_data:
                bazi_info = f"""
【用户生辰信息】
请基于以下实际数据进行精准分析，不要使用通用模板：
{json.dumps(request.bazi_data, ensure_ascii=False, indent=2)}
"""
                conversation_parts.append(bazi_info)
                print(f"📊 八字数据已添加到 prompt: {json.dumps(request.bazi_data, ensure_ascii=False)[:200]}...", flush=True)
            
            # 如果有额外的系统指令（如"起大运"指令），添加到 prompt 中
            if additional_instructions:
                conversation_parts.append("\n\n".join(additional_instructions))
            
            # 合并用户和助手消息，形成对话历史
            for i, user_msg in enumerate(user_messages):
                conversation_parts.append(f"用户：{user_msg}")
                if i < len(assistant_responses):
                    conversation_parts.append(f"助手：{assistant_responses[i]}")
            
            # 如果有最后一条用户消息，添加它
            if len(user_messages) > len(assistant_responses):
                conversation_parts.append(f"用户：{user_messages[-1]}")
            
            # 合并为完整 prompt
            full_prompt = "\n\n".join(conversation_parts)
            
            # 调用流式 API
            # Gemini API 的 generation_config 参数
            try:
                # 方法1：使用 config 参数（某些 SDK 版本）
                from google.genai import types
                stream = compass_client.models.generate_content_stream(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=8192,
                    )
                )
                print("✅ 使用 types.GenerateContentConfig 设置参数", flush=True)
            except (TypeError, AttributeError, ImportError) as e1:
                try:
                    # 方法2：使用字典格式的 config
                    stream = compass_client.models.generate_content_stream(
                        model=model_name,
                        contents=full_prompt,
                        config={
                            "temperature": 0.7,
                            "max_output_tokens": 8192,
                        }
                    )
                    print("✅ 使用字典格式 config 设置参数", flush=True)
                except (TypeError, AttributeError) as e2:
                    try:
                        # 方法3：直接传递参数
                        stream = compass_client.models.generate_content_stream(
                            model=model_name,
                            contents=full_prompt,
                            temperature=0.7,
                            max_output_tokens=8192
                        )
                        print("✅ 使用直接参数设置", flush=True)
                    except (TypeError, AttributeError) as e3:
                        # 方法4：使用默认参数（temperature 在 prompt 中控制）
                        print(f"⚠️  参数设置失败，使用默认参数: {e3}", flush=True)
                        stream = compass_client.models.generate_content_stream(
                            model=model_name,
                            contents=full_prompt
                        )
            
            # 3. 流式返回结果
            async def generate_response():
                full_text = ""
                try:
                    for chunk in stream:
                        chunk_text = ""
                        if hasattr(chunk, 'text'):
                            chunk_text = chunk.text
                        elif hasattr(chunk, 'candidates') and chunk.candidates:
                            if hasattr(chunk.candidates[0], 'content'):
                                if hasattr(chunk.candidates[0].content, 'parts'):
                                    for part in chunk.candidates[0].content.parts:
                                        if hasattr(part, 'text'):
                                            chunk_text += part.text
                        
                        if chunk_text:
                            full_text += chunk_text
                            yield f"data: {json.dumps({'type': 'text', 'content': chunk_text}, ensure_ascii=False)}\n\n"
                    
                    # 发送完成标记
                    yield "data: [DONE]\n\n"
                    print(f"✅ 起卦对话完成，总长度: {len(full_text)} 字符", flush=True)
                    
                except Exception as e:
                    print(f"❌ 流式输出错误: {e}", flush=True)
                    yield f"data: {json.dumps({'type': 'error', 'content': f'生成错误: {str(e)}'}, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(
                generate_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
            
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
            raise HTTPException(
                status_code=500,
                detail=f"AI 服务调用失败: {str(e)}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 起卦对话接口错误: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        raise HTTPException(
            status_code=500,
            detail=f"起卦对话失败: {str(e)}"
        )
