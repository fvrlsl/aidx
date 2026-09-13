"""种子数据：预建品牌实体 + 公开信息依据 + 热点案例 + 监控清单。

依据内容均来自公开报道的事实摘要，仅用于本地跑通链路；上线前应由运营核对来源。
用法：python -m app.seed
"""

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.main import ensure_default_admin
from app.models import CaseArticle, Evidence, HotWatchlist, Merchant, ProductBarcode
from app.services import entity_match
from app.services.rating_engine import recompute_merchant

MERCHANTS = [
    {"name": "胖东来", "aliases": ["胖东来商贸集团", "pangdonglai", "DL"], "industry": "零售商超", "region": "河南许昌",
     "intro": "河南许昌本土零售企业，以员工福利与服务口碑著称。", "usc": None},
    {"name": "信誉楼", "aliases": ["信誉楼百货", "信誉楼百货集团"], "industry": "零售商超", "region": "河北黄骅",
     "intro": "河北、山东、天津 44 家门店的百货连锁，员工不拿销售提成。", "usc": None},
    {"name": "麦当劳中国", "aliases": ["麦当劳", "金拱门", "McDonald's"], "industry": "连锁餐饮", "region": "全国",
     "intro": "外资连锁餐饮，连续多年获评中国杰出雇主。", "usc": None},
    {"name": "蜜雪冰城", "aliases": ["蜜雪", "MIXUE", "雪王"], "industry": "茶饮咖啡", "region": "全国", "intro": None, "usc": None},
    {"name": "海底捞", "aliases": ["海底捞火锅"], "industry": "连锁餐饮", "region": "全国", "intro": None, "usc": None},
    {"name": "山姆会员店", "aliases": ["山姆", "Sam's Club", "沃尔玛山姆"], "industry": "零售商超", "region": "全国", "intro": None, "usc": None},
    {"name": "京东", "aliases": ["京东集团", "JD.com", "京东物流"], "industry": "互联网/物流", "region": "北京", "intro": None, "usc": None},
    {"name": "老乡鸡", "aliases": ["老乡鸡快餐"], "industry": "连锁餐饮", "region": "安徽合肥", "intro": None, "usc": None},
    {"name": "霸王茶姬", "aliases": ["CHAGEE", "霸王茶姬奶茶"], "industry": "茶饮咖啡", "region": "全国", "intro": None, "usc": None},
    {"name": "瑞幸咖啡", "aliases": ["瑞幸", "luckin", "luckin coffee"], "industry": "茶饮咖啡", "region": "全国", "intro": None, "usc": None},
    {"name": "大疆", "aliases": ["大疆创新", "DJI"], "industry": "制造业", "region": "广东深圳", "intro": None, "usc": None},
    {"name": "美的集团", "aliases": ["美的", "Midea"], "industry": "制造业", "region": "广东佛山", "intro": None, "usc": None},
    {"name": "示例欠薪公司", "aliases": ["示例欠薪餐饮"], "industry": "连锁餐饮", "region": "示例", "intro": "用于本地演示负面评级链路的虚构主体。", "usc": None},
]

# (merchant, dimension, polarity, impact, summary, event_date, level, source_name, source_url)
EVIDENCE = [
    ("胖东来", "pay", 1, 2, "公布 37.93 亿元资产分配方案，覆盖全体 10194 名员工，普通员工人均约 20 万元份额。", date(2026, 3, 8), "B", "腾讯新闻/大河报", "https://news.qq.com/rain/a/20260311A06UT100"),
    ("胖东来", "hours", 1, 2, "推行 7 小时工作制与每年 40 天带薪休假，内部调研显示超八成员工选择维持现状而非降薪增假。", date(2026, 3, 8), "B", "大河报", "https://news.qq.com/rain/a/20260309A050K100"),
    ("胖东来", "dignity", 1, 1, "创始人在人民日报访谈中表示自 1999 年起将利润的 50% 分给员工，强调赋权一线员工。", date(2025, 8, 19), "B", "人民日报", "https://paper.people.com.cn/rmrb/pc/content/202508/19/content_30097056.html"),
    ("胖东来", "dignity", 1, 2, "公布员工人格尊严保护标准，对侮辱员工的行为设定经济补偿与法律追责。", date(2025, 11, 20), "B", "企业公告", "https://example.com/pdl-dignity"),
    ("信誉楼", "pay", 1, 1, "员工工资不与销售额挂钩、不拿销售提成，另设\"视客为友\"专项补贴。", date(2026, 9, 10), "B", "长城网", "https://heb.hebccw.cn/system/2026/09/10/102221376.shtml"),
    ("信誉楼", "dignity", 1, 1, "荣获全国\"诚信之星\"，为该奖项设立十年来首家百货连锁获奖企业；约 4 万员工。", date(2026, 9, 10), "B", "长城网", "https://heb.hebccw.cn/system/2026/09/10/102221376.shtml"),
    ("信誉楼", "dignity", 1, 1, "2025 年获评全国文明单位。", date(2025, 6, 1), "B", "长城网", "https://heb.hebccw.cn/system/2026/09/10/102221376.shtml"),
    ("麦当劳中国", "dignity", 1, 1, "第 16 次获评\"中国杰出雇主\"，连续第 6 年入选大学生喜爱的雇主品牌。", date(2026, 1, 16), "B", "麦当劳中国官网", "https://www.mcdonalds.com.cn/news/20260116-Top-Employer-2026"),
    ("麦当劳中国", "pay", 1, 1, "公开\"有保障、有福利、有发展\"的全面薪酬福利体系。", date(2026, 1, 16), "B", "麦当劳中国官网", "https://www.mcdonalds.com.cn/news/20260116-Top-Employer-2026"),
    ("麦当劳中国", "hours", 1, 1, "2025 年发布年轻人理想职场洞察报告，提出工作与生活平衡相关举措。", date(2025, 9, 1), "B", "麦当劳中国官网", "https://www.mcdonalds.com.cn/news/20260116-Top-Employer-2026"),
    ("京东", "pay", 1, 2, "为全职快递员缴纳五险一金，并公开宣布为外卖骑手缴纳社保。", date(2025, 2, 19), "B", "企业公告", "https://example.com/jd-social-insurance"),
    ("京东", "hours", -1, 1, "有员工在职场社区反映部分部门加班时长偏长。", date(2025, 5, 1), "C", "脉脉", "https://example.com/jd-maimai"),
    ("大疆", "hours", 1, 2, "多家媒体报道公司推行晚 9 点强制下班，管理层现场劝离加班员工。", date(2025, 2, 27), "B", "第一财经", "https://example.com/dji-9pm"),
    ("美的集团", "hours", 1, 1, "内部发文要求 18:20 后不得加班、反对形式主义。", date(2025, 3, 1), "B", "界面新闻", "https://example.com/midea-1820"),
    ("示例欠薪公司", "pay", -1, 2, "被列入拖欠农民工工资失信联合惩戒对象名单。", date(2026, 1, 15), "A", "人社部公示", "https://example.com/blacklist-1"),
    ("示例欠薪公司", "disputes", -1, 2, "因未依法支付劳动报酬受到劳动保障监察行政处罚。", date(2025, 11, 2), "A", "企业信用信息公示系统", "https://example.com/penalty-1"),
    ("示例欠薪公司", "disputes", -1, 1, "多起劳动争议仲裁裁决要求补发工资。", date(2025, 8, 20), "A", "裁判文书网", "https://example.com/court-1"),
    ("示例欠薪公司", "dignity", -1, 1, "有前员工在投诉平台反映管理层言语侮辱。", date(2026, 2, 1), "C", "黑猫投诉", "https://example.com/heimao-1"),
]

CASES = [
    {
        "title": "胖东来：把公司分给一万名员工",
        "subtitle": "37.93 亿元资产全员分配，7 小时工作制、40 天年假之后的又一步",
        "type": "benchmark",
        "merchants": ["胖东来"],
        "body": "2026 年 3 月 8 日，胖东来公布 37.93 亿元资产分配方案，管理团队与员工各约 50%，覆盖全体 10194 名员工，普通员工人均约 20 万元份额。\n\n同日公布的内部调研显示，在“降薪换假”与“维持现状”之间，超八成员工选择后者；97.55% 的员工对每年 40 天休假表示满意。\n\n从 2000 年首次推行利润共享，到如今把核心资产确权给全体员工，胖东来是国内“对员工好”话题最具代表性的样本。",
        "timeline": [
            {"date": "1999", "text": "创始人将当年利润 50% 分给员工", "source_url": "https://paper.people.com.cn/rmrb/pc/content/202508/19/content_30097056.html"},
            {"date": "2025-11", "text": "回应“制度过度严格”争议，公布员工尊严保护标准", "source_url": "https://news.qq.com/rain/a/20260309A050K100"},
            {"date": "2026-03-08", "text": "公布 37.93 亿元资产全员分配方案", "source_url": "https://news.qq.com/rain/a/20260311A06UT100"},
            {"date": "2026-03-10", "text": "创始人表示不追求商业帝国，立志成为“学校式企业”", "source_url": "https://news.qq.com/rain/a/20260311A06UT100"},
        ],
    },
    {
        "title": "信誉楼：不拿提成的导购，42 年的诚信复利",
        "subtitle": "全国“诚信之星”首家百货连锁获奖企业",
        "type": "benchmark",
        "merchants": ["信誉楼"],
        "body": "信誉楼有一条被视为“异类”的规定：员工工资不与销售额挂钩，不拿销售提成，另设“视客为友”专项补贴。\n\n2026 年 9 月，信誉楼获评全国“诚信之星”，是该奖项设立十年来首家百货连锁获奖企业。目前在河北、山东、天津拥有 44 家门店、约 4 万名员工。",
        "timeline": [
            {"date": "2021", "text": "入选“诚信兴商十大案例”", "source_url": "https://heb.hebccw.cn/system/2026/09/10/102221376.shtml"},
            {"date": "2025", "text": "获评全国文明单位", "source_url": "https://heb.hebccw.cn/system/2026/09/10/102221376.shtml"},
            {"date": "2026-09", "text": "获评全国“诚信之星”", "source_url": "https://heb.hebccw.cn/system/2026/09/10/102221376.shtml"},
        ],
    },
    {
        "title": "反内卷之年：强制下班的大厂们",
        "subtitle": "大疆 9 点清场、美的 18:20 下班，制度能否落地仍待观察",
        "type": "reversal",
        "merchants": ["大疆", "美的集团"],
        "body": "2025 年初，多家制造业头部企业相继公开“强制下班”举措。大疆被报道推行晚 9 点强制下班；美的集团内部发文要求 18:20 后不得加班并反对形式主义。\n\n这类举措的真实落地情况需要持续跟踪，我们会持续收集员工侧的反馈。",
        "timeline": [
            {"date": "2025-02-27", "text": "大疆晚 9 点强制下班被媒体报道", "source_url": "https://example.com/dji-9pm"},
            {"date": "2025-03", "text": "美的集团发文要求 18:20 后不得加班", "source_url": "https://example.com/midea-1820"},
        ],
    },
    {
        "title": "示例：一家上了欠薪黑名单的餐饮公司",
        "subtitle": "用于演示负面评级链路的虚构案例",
        "type": "warning",
        "merchants": ["示例欠薪公司"],
        "body": "本案例为虚构，用于本地演示 A 级负面依据如何形成“存在严重问题”评级以及商家反馈流程。",
        "timeline": [
            {"date": "2025-08", "text": "多起劳动仲裁裁决补发工资", "source_url": "https://example.com/court-1"},
            {"date": "2025-11", "text": "受到劳动保障监察行政处罚", "source_url": "https://example.com/penalty-1"},
            {"date": "2026-01", "text": "被列入拖欠工资失信联合惩戒名单", "source_url": "https://example.com/blacklist-1"},
        ],
    },
]

WATCHLIST = [
    ("胖东来", ["胖东来", "于东来"], "P0"),
    ("信誉楼", ["信誉楼"], "P1"),
    ("麦当劳中国", ["麦当劳 员工", "麦当劳 雇主"], "P1"),
    ("蜜雪冰城", ["蜜雪冰城 员工", "蜜雪冰城 加班"], "P1"),
    ("海底捞", ["海底捞 员工"], "P1"),
    ("京东", ["京东 骑手 社保", "京东 快递员"], "P1"),
]

BARCODES = [("6921168509256", "农夫山泉 550ml（示例映射）", "示例欠薪公司"), ("6901028075831", "示例商品", "蜜雪冰城")]


def run() -> None:
    init_db()
    ensure_default_admin()
    with SessionLocal() as db:
        if db.execute(select(Merchant.id)).first():
            print("已有数据，跳过种子导入")
            return
        by_name: dict[str, Merchant] = {}
        for m in MERCHANTS:
            row = Merchant(canonical_name=m["name"], industry=m["industry"], region=m["region"], intro=m["intro"],
                           unified_social_credit_code=m["usc"], status="published", created_by="editor")
            db.add(row)
            db.flush()
            for alias in [m["name"], *m["aliases"]]:
                entity_match.add_alias(db, row.id, alias)
            by_name[m["name"]] = row

        now = datetime.now(timezone.utc)
        for name, dim, pol, imp, summary, d, level, sname, surl in EVIDENCE:
            db.add(Evidence(merchant_id=by_name[name].id, dimension=dim, polarity=pol, impact=imp * pol, summary=summary,
                            event_date=d, source_level=level, source_name=sname, source_url=surl, status="approved",
                            reviewed_by="seed", reviewed_at=now, confidence=1.0))
        db.flush()
        for m in by_name.values():
            recompute_merchant(db, m.id, operator="seed")

        for c in CASES:
            db.add(CaseArticle(title=c["title"], subtitle=c["subtitle"], type=c["type"], body=c["body"], timeline=c["timeline"],
                               merchant_ids=[by_name[n].id for n in c["merchants"]], status="published", published_at=now))
        for name, kws, pri in WATCHLIST:
            db.add(HotWatchlist(merchant_id=by_name[name].id, keywords=kws, priority=pri))
        for code, pname, mname in BARCODES:
            db.add(ProductBarcode(barcode=code, product_name=pname, merchant_id=by_name[mname].id))
        db.commit()
        print(f"种子导入完成：{len(MERCHANTS)} 个商家，{len(EVIDENCE)} 条依据，{len(CASES)} 个案例")


if __name__ == "__main__":
    run()
