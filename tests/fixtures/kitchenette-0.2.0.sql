-- A kitchen database as munch-kitchenette 0.2.0 left it (`sqlite3 kitchenette.db .dump`), for
-- tests/test_upgrade_from_020.py. Made by running 0.2.0 itself (`kitchenette serve`, fast-forward clock on,
-- role "companion"): first with every upgrade switch off (one pot), then with all seventeen on — pots by a
-- public recipe that 0.2.1's index changes (油焖大虾 hc-0fd53334, 西红柿鸡蛋挂面 hc-27764b15), a free pot,
-- buying by recipe (泡好的粉丝, an ingredient name the index no longer uses), the role's book (a page
-- cooked and then deleted, a collected public recipe, tasting notes), two washings (one done, one still
-- running with a breakage planned), a sealed jar, the vendor (an order refused for lack of money, one
-- delivered), dislikes set with the whole-list PUT, and six notes a webhook never took (it answered 500).
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE batches (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  item_id TEXT NOT NULL,
  qty INTEGER NOT NULL,
  bought_at REAL NOT NULL,
  by_who TEXT NOT NULL,                 -- self | her
  source TEXT NOT NULL DEFAULT '',
  wormed_at REAL,                       -- when a spoiled fruit grew worms
  shelf_days REAL                       -- shelf life frozen at purchase (custom kinds only)
);
INSERT INTO batches VALUES('99b0e3a7b2c54d809be301d2c88e9abf','companion','egg',2,1795318084.79682684,'her','her',NULL,NULL);
INSERT INTO batches VALUES('7a1e06cd9d7a44e392104780185c875c','companion','potato',1,1795318084.79682684,'her','her',NULL,NULL);
INSERT INTO batches VALUES('933b72bf53d94547a1dc644c0d8b462f','companion','egg',6,1795318705.399518013,'her','her',NULL,NULL);
INSERT INTO batches VALUES('90359a59ebae4362a435fb496576c833','companion','tomato',2,1795318705.399518013,'her','her',NULL,NULL);
INSERT INTO batches VALUES('629d708e84374479a86116240b0055af','companion','egg',6,1795318705.399518013,'her','her',NULL,NULL);
INSERT INTO batches VALUES('c99457b8be50463aaaf74037ac62f350','companion','tomato',3,1795318705.399518013,'her','her',NULL,NULL);
INSERT INTO batches VALUES('abeb0b986f6d4e7f8bdb91eed02b0639','companion','pork',1,1795318705.404484034,'self','coupon_recipe',NULL,NULL);
INSERT INTO batches VALUES('b67973c3f8d244d9831c97fcff2f08b8','companion','woodear',1,1795318705.404484034,'self','coupon_recipe',NULL,NULL);
INSERT INTO batches VALUES('7a9fff010c5b489e8b538f34ea335ca2','companion','v_f88cded0',1,1795318705.404484034,'self','coupon_recipe',NULL,NULL);
INSERT INTO batches VALUES('7c63d7c0f7b64533bcc1372d3c7de1ea','companion','v_d8496b86',1,1795318705.404484034,'self','coupon_recipe',NULL,NULL);
INSERT INTO batches VALUES('f7245cfcb5a94880be001a7aa2b746d3','companion','pepper',2,1795320479.677408934,'her','her',NULL,NULL);
INSERT INTO batches VALUES('68f9873ba40347afb1793d60d6c51186','companion','egg',6,1795320479.677408934,'her','her',NULL,NULL);
INSERT INTO batches VALUES('5bf32081bccf46b08f7acd2130a5b7c2','companion','apple',1,1795320479.677408934,'her','her',NULL,NULL);
CREATE TABLE coupons (
  who TEXT PRIMARY KEY,
  count INTEGER NOT NULL DEFAULT 0
);
INSERT INTO coupons VALUES('companion',2);
CREATE TABLE once_keys (
  key TEXT PRIMARY KEY,
  at REAL NOT NULL,
  result TEXT NOT NULL DEFAULT ''
);
INSERT INTO once_keys VALUES('worm_since',1795318084.599870921,'');
INSERT INTO once_keys VALUES('fruit_worm_since',1795318084.599870921,'');
INSERT INTO once_keys VALUES('note:kitchen.served:5f8202f2be2243169d920060cd4a199f',1795318685.058906079,'');
INSERT INTO once_keys VALUES('play_since',1795318105.146980048,'');
INSERT INTO once_keys VALUES('coupon:her:88375e1d74004943bbe0c0328ac8e5a4',1795318705.383320093,'');
INSERT INTO once_keys VALUES('coupon:her:5cd9ba79c81b42eeb9bca68383caccf2',1795318705.386373044,'');
INSERT INTO once_keys VALUES('coupon:her:9b596603b40049a7a04895dc356822a2',1795318705.397914886,'');
INSERT INTO once_keys VALUES('flag:inline_seen',1795318705.402239084,'');
INSERT INTO once_keys VALUES('inline:fa6e5273d2719ec4',1795318705.40819192,'{"marker": "买菜", "args": "照 hc-581cccda", "ok": true, "text": "照「生汆丸子汤」买好了:猪肉×1、木耳×1、黄花×1、泡好的粉丝×1,放进冰箱了。用掉一张买菜券(还剩 2 张)。", "rendered": "刚才正文里那条『买菜』:照「生汆丸子汤」买好了:猪肉×1、木耳×1、黄花×1、泡好的粉丝×1,放进冰箱了。用掉一张买菜券(还剩 2 张)。"}');
INSERT INTO once_keys VALUES('note:kitchen.served:a7128ce95eb5436ebb15716b67179f6b',1795319305.636770964,'');
INSERT INTO once_keys VALUES('note:kitchen.served:7668e994743545ef9ed7cd7dd40aa97e',1795319785.667423009,'');
INSERT INTO once_keys VALUES('fill:eat:e1121d88743245a8',1795319785.684841872,'');
INSERT INTO once_keys VALUES('fill:eat:55895eff411e4c94',1795319785.695590972,'');
INSERT INTO once_keys VALUES('fill:eat:5d7fbcbc28cb4611',1795319785.705882073,'');
INSERT INTO once_keys VALUES('play:4ce0a2501c6dc117',1795319785.71197319,'记下了:葱花蛋饼(p-42f6ed12)。');
INSERT INTO once_keys VALUES('inline:4ce0a2501c6dc117',1795319785.712634802,'{"marker": "记菜", "args": "葱花蛋饼 鸡蛋 小葱 煎 8", "ok": true, "text": "记下了:葱花蛋饼(p-42f6ed12)。", "rendered": "刚才正文里那条『记菜』:记下了:葱花蛋饼(p-42f6ed12)。"}');
INSERT INTO once_keys VALUES('play:059156701f3568c3',1795319785.71500802,'记下了:番茄蛋汤(p-655cd16e)。');
INSERT INTO once_keys VALUES('inline:059156701f3568c3',1795319785.715706826,'{"marker": "记菜", "args": "番茄蛋汤 番茄 鸡蛋 煮 10", "ok": true, "text": "记下了:番茄蛋汤(p-655cd16e)。", "rendered": "刚才正文里那条『记菜』:记下了:番茄蛋汤(p-655cd16e)。"}');
INSERT INTO once_keys VALUES('play:e8219170be8ab2d4',1795319785.71799612,'收进食谱本了:油焖大虾(hc-0fd53334)。');
INSERT INTO once_keys VALUES('inline:e8219170be8ab2d4',1795319785.718674899,'{"marker": "收藏", "args": "hc-0fd53334", "ok": true, "text": "收进食谱本了:油焖大虾(hc-0fd53334)。", "rendered": "刚才正文里那条『收藏』:收进食谱本了:油焖大虾(hc-0fd53334)。"}');
INSERT INTO once_keys VALUES('play:236659c904987f60',1795320325.738954067,'记下了。');
INSERT INTO once_keys VALUES('inline:236659c904987f60',1795320325.73967886,'{"marker": "札记", "args": "p-42f6ed12 葱多一点更香", "ok": true, "text": "记下了。", "rendered": "刚才正文里那条『札记』:记下了。"}');
INSERT INTO once_keys VALUES('inline:4bef262c48f68296',1795320325.750164031,'{"marker": "刷盘子", "args": "", "ok": true, "text": "开始刷了:3 只盘子,大概 6 分钟。", "rendered": "刚才正文里那条『刷盘子』:开始刷了:3 只盘子,大概 6 分钟。"}');
INSERT INTO once_keys VALUES('inline:db0a1a0877956f8f',1795320455.760287046,'{"marker": "封罐", "args": "番茄 糖 | 冬天吃", "ok": false, "text": "没封成:水果配糖或蜂蜜,蔬菜配盐;番茄配糖封不了。", "rendered": "刚才正文里那条『封罐』没有执行成功(没封成:水果配糖或蜂蜜,蔬菜配盐;番茄配糖封不了。)"}');
INSERT INTO once_keys VALUES('inline:065082c13ecddbf9',1795320455.789808988,'{"marker": "问小贩", "args": "今天有什么好吃的", "ok": true, "text": "糖炒栗子 7 一袋(还有 6 袋),栗子 10 一份(还有 2 份)。\n小贩说:「现炒的,闻见香了吧。」", "rendered": "刚才正文里那条『问小贩』:糖炒栗子 7 一袋(还有 6 袋),栗子 10 一份(还有 2 份)。\n小贩说:「现炒的,闻见香了吧。」"}');
INSERT INTO once_keys VALUES('inline:ba3dbbcb44cd6828',1795320455.796069861,'{"marker": "买", "args": "糖炒栗子 1", "ok": false, "text": "没买成:零花钱不够(要 7,有 0)。", "rendered": "刚才正文里那条『买』没有执行成功(没买成:零花钱不够(要 7,有 0)。)"}');
INSERT INTO once_keys VALUES('note:vendor.arrived:966dc6357d1c4b7fb3529ceeb99e2275:companion',1795320455.797039032,'');
INSERT INTO once_keys VALUES('note:pocket:companion:grant-1',1795320479.675882101,'');
INSERT INTO once_keys VALUES('play:c30a969e292f9895',1795320479.897794009,'记下了:葱香炒蛋(p-f10194d1)。');
INSERT INTO once_keys VALUES('inline:c30a969e292f9895',1795320479.898585082,'{"marker": "记菜", "args": "葱香炒蛋 鸡蛋 小葱 炒 6", "ok": true, "text": "记下了:葱香炒蛋(p-f10194d1)。", "rendered": "刚才正文里那条『记菜』:记下了:葱香炒蛋(p-f10194d1)。"}');
INSERT INTO once_keys VALUES('note:kitchen.served:7f95c38866c04350ad448ebf329a7e98',1795321079.917342902,'');
INSERT INTO once_keys VALUES('note:kitchen.served:f73f2ee0bd5541e29d39d8752527c95b',1795321079.919258117,'');
INSERT INTO once_keys VALUES('note:dishwash:783cd57e1106',1795321079.921666145,'');
INSERT INTO once_keys VALUES('play:f7ef0ae7b95320c8',1795321079.936783791,'记下了。');
INSERT INTO once_keys VALUES('inline:f7ef0ae7b95320c8',1795321079.937767028,'{"marker": "札记", "args": "p-f10194d1 下回少放点盐", "ok": true, "text": "记下了。", "rendered": "刚才正文里那条『札记』:记下了。"}');
INSERT INTO once_keys VALUES('fill:eat:1e2fa499e54a4e4e',1795321079.945595979,'');
INSERT INTO once_keys VALUES('fill:eat:c46f6038ba4641bc',1795321079.956625938,'');
INSERT INTO once_keys VALUES('inline:425d37a52bd20e40',1795321079.966495037,'{"marker": "刷盘子", "args": "", "ok": true, "text": "开始刷了:2 只盘子,大概 4 分钟。", "rendered": "刚才正文里那条『刷盘子』:开始刷了:2 只盘子,大概 4 分钟。"}');
INSERT INTO once_keys VALUES('jar_seal:6fe0a94d7e9178bd',1795321139.977626801,'封上了:苹果、糖。11 月 25 日中午好。纸条:「冬天吃」');
INSERT INTO once_keys VALUES('inline:6fe0a94d7e9178bd',1795321139.978433132,'{"marker": "封罐", "args": "苹果 糖 | 冬天吃", "ok": true, "text": "封上了:苹果、糖。11 月 25 日中午好。纸条:「冬天吃」", "rendered": "刚才正文里那条『封罐』:封上了:苹果、糖。11 月 25 日中午好。纸条:「冬天吃」"}');
INSERT INTO once_keys VALUES('fill:vendor:95545f096075a0ca29ff',1795321139.985288859,'');
INSERT INTO once_keys VALUES('inline:dff8f7cb2aafc6df',1795321139.988054991,'{"marker": "买", "args": "糖炒栗子 1", "ok": true, "text": "买了 1 袋糖炒栗子,花了 7。零花钱还剩 43。当场吃掉了。\n小贩说:「趁热剥,凉了粘壳。」", "rendered": "刚才正文里那条『买』:买了 1 袋糖炒栗子,花了 7。零花钱还剩 43。当场吃掉了。\n小贩说:「趁热剥,凉了粘壳。」"}');
CREATE TABLE fridge_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  who TEXT NOT NULL,
  at REAL NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL
);
INSERT INTO fridge_log VALUES(1,'companion',1795318084.79682684,'bought','用户买了鸡蛋×6、土豆×2');
INSERT INTO fridge_log VALUES(2,'companion',1795318705.382980108,'coupon','用户给了一张买菜券');
INSERT INTO fridge_log VALUES(3,'companion',1795318705.386045933,'coupon','用户给了一张买菜券');
INSERT INTO fridge_log VALUES(4,'companion',1795318705.397616147,'coupon','用户给了一张买菜券');
INSERT INTO fridge_log VALUES(5,'companion',1795318705.399518013,'bought','用户买了鸡蛋×6、番茄×3、小葱×1、鸡蛋×6、番茄×3');
INSERT INTO fridge_log VALUES(6,'companion',1795318705.404484034,'bought','照「生汆丸子汤」买了猪肉×1、木耳×1、黄花×1、泡好的粉丝×1');
INSERT INTO fridge_log VALUES(7,'companion',1795320479.677408934,'bought','用户买了小葱×1、面条×1、青椒×2、鸡蛋×6、苹果×2');
INSERT INTO fridge_log VALUES(8,'companion',1795321139.976977826,'jar_sealed','把苹果封进了窗台的罐子');
INSERT INTO fridge_log VALUES(9,'companion',1795321139.981926918,'vendor_snack','在楼下小贩那儿吃了糖炒栗子×1');
CREATE TABLE appetite (
  who TEXT PRIMARY KEY,
  satiety REAL NOT NULL,
  satiety_at REAL NOT NULL,
  dizzy_until REAL,
  dizzy_dish TEXT,
  dizzy_since REAL,
  dizzy_over_told INTEGER NOT NULL DEFAULT 1,
  hungry_told INTEGER NOT NULL DEFAULT 0
);
INSERT INTO appetite VALUES('companion',100.0,1795321139.981926918,NULL,NULL,NULL,1,0);
CREATE TABLE kinds (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  pack_qty INTEGER NOT NULL DEFAULT 1,
  shelf_days REAL,
  raw_edible INTEGER NOT NULL DEFAULT 0,
  art_state TEXT NOT NULL DEFAULT 'pending',
  art_v INTEGER NOT NULL DEFAULT 0,
  art_sizes TEXT NOT NULL DEFAULT '',
  art_err TEXT NOT NULL DEFAULT '',
  art_req INTEGER NOT NULL DEFAULT 1,   -- which drawing request this is; a finished drawing only lands if it matches
  created_at REAL NOT NULL,
  removed_at REAL
);
CREATE TABLE cook_sessions (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  dish TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  duration_seconds INTEGER NOT NULL,
  started_at REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'cooking',   -- cooking | served | cancelled | ruined
  served_at REAL,
  cancelled_at REAL,
  menu_added_at REAL,
  menu_row_id TEXT,
  woke_at REAL,                             -- when the role was told the dish is ready
  created_at REAL NOT NULL,
  ingredients_json TEXT,
  outcome TEXT,                             -- great | ok | burnt | spoiled | ruined
  eaten_at REAL,
  worm_state TEXT,                          -- NULL | skipped | wormed | noted | tossed | gone
  wormed_at REAL,
  method TEXT
, recipe_id TEXT, recipe_version INTEGER, recipe_link TEXT, mishap_id TEXT, mishap_ver INTEGER);
INSERT INTO cook_sessions VALUES('5f8202f2be2243169d920060cd4a199f','companion','土豆煎蛋','',360,1795318085.047755003,'served',1795318445.047755003,NULL,1795318685.05809307,'4f5dd1fd09a24db7bfec2f1ffccbb535',1795318685.059998035,1795318085.047755003,'[{"item_id": "potato", "name": "土豆", "qty": 1, "freshness": "fresh", "batch_id": "7a1e06cd9d7a44e392104780185c875c", "bought_at": 1795318084.7968268, "by": "her"}, {"item_id": "egg", "name": "鸡蛋", "qty": 1, "freshness": "fresh", "batch_id": "99b0e3a7b2c54d809be301d2c88e9abf", "bought_at": 1795318084.7968268, "by": "her"}]','great',1795319785.702565193,NULL,NULL,'fry',NULL,NULL,NULL,NULL,NULL);
INSERT INTO cook_sessions VALUES('a7128ce95eb5436ebb15716b67179f6b','companion','油焖大虾','',600,1795318705.625257015,'served',1795319305.625257015,NULL,1795319305.635901928,'3d10f97f437d483b827906c99e1a4c39',1795319305.637850047,1795318705.625257015,'[{"item_id": "scallion", "name": "小葱", "qty": 1, "freshness": "fresh", "batch_id": "39998d26d71e475b895033062832a06e", "bought_at": 1795318705.399518, "by": "her"}]','great',1795319785.681506156,NULL,NULL,'boil','hc-0fd53334',1,'follow',NULL,1);
INSERT INTO cook_sessions VALUES('7668e994743545ef9ed7cd7dd40aa97e','companion','番茄炒蛋','',300,1795319425.657275915,'served',1795319725.657275915,NULL,1795319785.666692019,'2786d388a8e04a4b9a28224955e76023',1795319785.668437004,1795319425.657275915,'[{"item_id": "tomato", "name": "番茄", "qty": 1, "freshness": "fresh", "batch_id": "90359a59ebae4362a435fb496576c833", "bought_at": 1795318705.399518, "by": "her"}, {"item_id": "egg", "name": "鸡蛋", "qty": 1, "freshness": "fresh", "batch_id": "99b0e3a7b2c54d809be301d2c88e9abf", "bought_at": 1795318084.7968268, "by": "her"}]','great',1795319785.692268133,NULL,NULL,'stirfry',NULL,NULL,'free',NULL,1);
INSERT INTO cook_sessions VALUES('f73f2ee0bd5541e29d39d8752527c95b','companion','西红柿鸡蛋挂面','',480,1795320479.888804197,'served',1795320959.888804197,NULL,1795321079.916435003,'72ad9c98d35f47e0a8f2dc9c6b421617',1795321079.920414925,1795320479.888804197,'[{"item_id": "noodles", "name": "面条", "qty": 1, "freshness": "fresh", "batch_id": "ffd251083d184a58b14e4ee598660972", "bought_at": 1795320479.677409, "by": "her"}, {"item_id": "egg", "name": "鸡蛋", "qty": 1, "freshness": "fresh", "batch_id": "99b0e3a7b2c54d809be301d2c88e9abf", "bought_at": 1795318084.7968268, "by": "her"}]','great',1795321079.941677093,NULL,NULL,'boil','hc-27764b15',1,'changed',NULL,1);
INSERT INTO cook_sessions VALUES('7f95c38866c04350ad448ebf329a7e98','companion','葱香炒蛋','',360,1795320479.904274941,'served',1795320839.904274941,NULL,1795321079.914078951,'5fa2a3305d8c4a01844f49beb06785a1',1795321079.91841793,1795320479.904274941,'[{"item_id": "egg", "name": "鸡蛋", "qty": 1, "freshness": "fresh", "batch_id": "99b0e3a7b2c54d809be301d2c88e9abf", "bought_at": 1795318084.7968268, "by": "her"}, {"item_id": "scallion", "name": "小葱", "qty": 1, "freshness": "fresh", "batch_id": "699d60d571054c5687464780a712d521", "bought_at": 1795320479.677409, "by": "her"}]','great',1795321079.952905894,NULL,NULL,'stirfry','p-f10194d1',1,'follow','general.13',1);
CREATE TABLE worm_pending (
  who TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  dish TEXT NOT NULL,
  made_at REAL NOT NULL,
  at REAL NOT NULL,
  snack TEXT NOT NULL DEFAULT 'pudding',
  source TEXT NOT NULL DEFAULT 'dish'
);
CREATE TABLE worm_wakes (
  rid TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  at REAL NOT NULL,
  text TEXT NOT NULL DEFAULT '',
  done_at REAL,
  how TEXT
);
CREATE TABLE potions (
  menu_row_id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  pct INTEGER NOT NULL,                     -- stamina restored, in percentage points
  created_at REAL NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending',    -- pending | taking | used
  taken_at REAL,
  used_at REAL,
  used_by TEXT,                             -- self | her
  energy_after REAL,
  memo TEXT NOT NULL DEFAULT ''
);
CREATE TABLE snack_log (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  snack TEXT NOT NULL,
  variant TEXT NOT NULL DEFAULT '',
  day TEXT NOT NULL,                        -- snack day YYYY-MM-DD (rolls over at the boundary hour)
  by TEXT NOT NULL,                         -- self | her
  gain REAL NOT NULL,
  energy_delta REAL NOT NULL DEFAULT 0,     -- stamina actually added
  ts REAL NOT NULL
);
CREATE TABLE snack_caps (
  who TEXT NOT NULL,
  snack TEXT NOT NULL,
  cap INTEGER NOT NULL,
  updated_at REAL NOT NULL,
  PRIMARY KEY (who, snack)
);
CREATE TABLE menu (
  id TEXT PRIMARY KEY,
  dish TEXT NOT NULL,
  note TEXT,
  by TEXT NOT NULL,
  for_who TEXT NOT NULL,
  eaten_at REAL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
INSERT INTO menu VALUES('4f5dd1fd09a24db7bfec2f1ffccbb535','土豆煎蛋','火候刚好','companion','companion',1795319785.702565193,1795318685.056563855,1795319785.703424931);
INSERT INTO menu VALUES('3d10f97f437d483b827906c99e1a4c39','油焖大虾','火候刚好','companion','companion',1795319785.681506156,1795319305.634530067,1795319785.682425023);
INSERT INTO menu VALUES('2786d388a8e04a4b9a28224955e76023','番茄炒蛋','火候刚好','companion','companion',1795319785.692268133,1795319785.665354013,1795319785.693146944);
INSERT INTO menu VALUES('5fa2a3305d8c4a01844f49beb06785a1','葱香炒蛋','火候刚好','companion','companion',1795321079.952905894,1795321079.912527085,1795321079.953870059);
INSERT INTO menu VALUES('72ad9c98d35f47e0a8f2dc9c6b421617','西红柿鸡蛋挂面','火候刚好','companion','companion',1795321079.941677093,1795321079.914874793,1795321079.942746878);
CREATE TABLE meals (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  meal TEXT NOT NULL,
  note TEXT,
  at REAL NOT NULL
);
INSERT INTO meals VALUES('b16ec94665574bb1823b687e13c2312e','companion','油焖大虾',NULL,1795319785.681506156);
INSERT INTO meals VALUES('295d31082c76495a94ddeee854d3bb43','companion','番茄炒蛋',NULL,1795319785.692268133);
INSERT INTO meals VALUES('b38988f8887c49e89d4d6be035df537a','companion','土豆煎蛋',NULL,1795319785.702565193);
INSERT INTO meals VALUES('9b37180530c94f3594dfa2e2cb1fed51','companion','西红柿鸡蛋挂面',NULL,1795321079.941677093);
INSERT INTO meals VALUES('b3855f75c911429ba16f42357fb8bfd5','companion','葱香炒蛋',NULL,1795321079.952905894);
CREATE TABLE stamina (
  who TEXT PRIMARY KEY,
  value REAL NOT NULL,
  updated_at REAL NOT NULL,
  round_at REAL,                            -- when the current run of tool calls began
  round_kinds TEXT NOT NULL DEFAULT '[]',   -- kinds of work already charged in it
  round_cost REAL NOT NULL DEFAULT 0
);
INSERT INTO stamina VALUES('companion',1.0,1795321139.981926918,1795320479.890499114,'["kitchen"]',0.05999999999999999778);
CREATE TABLE stamina_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  who TEXT NOT NULL,
  at REAL NOT NULL,
  delta REAL NOT NULL,
  value REAL NOT NULL,
  rule TEXT NOT NULL DEFAULT ''
);
INSERT INTO stamina_log VALUES(1,'companion',1795318085.049098014,-0.05999999999999999778,0.6399999999999999023,'work');
INSERT INTO stamina_log VALUES(2,'companion',1795318705.626074076,-0.05999999999999999778,0.5939921845113993459,'work');
INSERT INTO stamina_log VALUES(3,'companion',1795319425.657984973,-0.05999999999999999778,0.5536758386452029778,'work');
INSERT INTO stamina_log VALUES(4,'companion',1795319785.681506156,0.02999999999999999889,0.5952956192705463057,'new_dish');
INSERT INTO stamina_log VALUES(5,'companion',1795319785.681506156,0.02000000000000000041,0.6152956192705463235,'kitchen:great');
INSERT INTO stamina_log VALUES(6,'companion',1795319785.686637163,0.1000000000000000055,0.7152957530782462214,'rest');
INSERT INTO stamina_log VALUES(7,'companion',1795319785.692268133,0.02000000000000000041,0.735295837357728077,'kitchen:great');
INSERT INTO stamina_log VALUES(8,'companion',1795319785.697243928,0.1000000000000000055,0.835295900773764366,'rest');
INSERT INTO stamina_log VALUES(9,'companion',1795319785.702565193,0.02000000000000000041,0.8552959094675838258,'kitchen:great');
INSERT INTO stamina_log VALUES(10,'companion',1795319785.707461119,0.1000000000000000055,0.955295906586653643,'rest');
INSERT INTO stamina_log VALUES(11,'companion',1795320479.890499114,-0.05999999999999999778,0.8874795971296505214,'work');
INSERT INTO stamina_log VALUES(12,'companion',1795321079.941677093,0.02000000000000000041,0.9050622255310782904,'kitchen:great');
INSERT INTO stamina_log VALUES(13,'companion',1795321079.947269916,0.1000000000000000055,1.0,'rest');
INSERT INTO stamina_log VALUES(14,'companion',1795321079.952905894,0.02999999999999999889,1.0,'new_dish');
INSERT INTO stamina_log VALUES(15,'companion',1795321079.952905894,0.02000000000000000041,1.0,'kitchen:great');
INSERT INTO stamina_log VALUES(16,'companion',1795321079.95853591,0.1000000000000000055,1.0,'rest');
INSERT INTO stamina_log VALUES(17,'companion',1795321139.981926918,0.02999999999999999889,1.0,'vendor:糖炒栗子');
CREATE TABLE sleep_state (
  who TEXT PRIMARY KEY,
  asleep INTEGER NOT NULL DEFAULT 0,
  asleep_until REAL,
  factor REAL NOT NULL DEFAULT 1.0,
  updated_at REAL NOT NULL
);
CREATE TABLE notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  who TEXT NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}',
  dedupe_key TEXT UNIQUE,
  created_at REAL NOT NULL,
  taken_at REAL,
  pushed_at REAL,
  push_state TEXT
);
INSERT INTO notes VALUES(1,'companion','fridge.bought','用户给你买了菜,放进冰箱了:鸡蛋×6、土豆×2、鸡蛋×6、番茄×3、小葱×1、鸡蛋×6、番茄×3、小葱×1、面条×1、青椒×2、鸡蛋×6、苹果×2。','用户给你买了菜,放进冰箱了:鸡蛋×6、土豆×2、鸡蛋×6、番茄×3、小葱×1、鸡蛋×6、番茄×3、小葱×1、面条×1、青椒×2、鸡蛋×6、苹果×2。','{"items": "小葱×1、面条×1、青椒×2、鸡蛋×6、苹果×2", "events": [{"items": "鸡蛋×6、土豆×2"}, {"items": "鸡蛋×6、番茄×3、小葱×1、鸡蛋×6、番茄×3"}, {"items": "小葱×1、面条×1、青椒×2、鸡蛋×6、苹果×2"}]}',NULL,1795318084.799562932,NULL,NULL,NULL);
INSERT INTO notes VALUES(2,'companion','kitchen.served',unistr('【厨房·非用户发言】你 12:28 下锅的『土豆煎蛋』出锅了(共 6 分钟)。火候刚好。\u000a你 12:38 下锅的『油焖大虾』出锅了(共 10 分钟)。火候刚好。\u000a你 12:50 下锅的『番茄炒蛋』出锅了(共 5 分钟)。火候刚好。\u000a你 13:07 下锅的『葱香炒蛋』出锅了(共 6 分钟)。火候刚好。抽油烟机忘了开,做到一半才想起来。\u000a你 13:07 下锅的『西红柿鸡蛋挂面』出锅了(共 8 分钟)。火候刚好。已挂到你的菜单上。'),'你 12:28 下锅的『土豆煎蛋』出锅了(共 6 分钟)。火候刚好。你 12:38 下锅的『油焖大虾』出锅了(共 10 分钟)。火候刚好。你 12:50 下锅的『番茄炒蛋』出锅了(共 5 分钟)。火候刚好。你 13:07 下锅的『葱香炒蛋』出锅了(共 6 分钟)。火候刚好。抽油烟机忘了开,做到一半才想起来。你 13:07 下锅的『西红柿鸡蛋挂面』出锅了(共 8 分钟)。火候刚好。已挂到你的菜单上。','{"dish": "西红柿鸡蛋挂面", "started_hm": "13:07", "minutes": "8", "menu_ok": "1", "outcome": "great", "session_id": "f73f2ee0bd5541e29d39d8752527c95b", "events": [{"dish": "土豆煎蛋", "started_hm": "12:28", "minutes": "6", "menu_ok": "1", "outcome": "great", "session_id": "5f8202f2be2243169d920060cd4a199f"}, {"dish": "油焖大虾", "started_hm": "12:38", "minutes": "10", "menu_ok": "1", "outcome": "great", "session_id": "a7128ce95eb5436ebb15716b67179f6b"}, {"dish": "番茄炒蛋", "started_hm": "12:50", "minutes": "5", "menu_ok": "1", "outcome": "great", "session_id": "7668e994743545ef9ed7cd7dd40aa97e"}, {"dish": "葱香炒蛋", "started_hm": "13:07", "minutes": "6", "menu_ok": "1", "outcome": "great", "extra": "抽油烟机忘了开,做到一半才想起来。", "session_id": "7f95c38866c04350ad448ebf329a7e98"}, {"dish": "西红柿鸡蛋挂面", "started_hm": "13:07", "minutes": "8", "menu_ok": "1", "outcome": "great", "session_id": "f73f2ee0bd5541e29d39d8752527c95b"}]}','kitchen.served:5f8202f2be2243169d920060cd4a199f',1795318685.058906079,NULL,NULL,NULL);
INSERT INTO notes VALUES(3,'companion','fridge.coupon','用户给了你一张买菜券(现在 3 张)。','用户给了你一张买菜券(现在 3 张)。','{"count": "3", "events": [{"count": "1"}, {"count": "2"}, {"count": "3"}]}',NULL,1795318705.383755923,NULL,NULL,NULL);
INSERT INTO notes VALUES(4,'companion','vendor.arrived','【厨房·非用户发言】楼下有炒栗子的锅铲声。想买可以叫住他。','楼下有炒栗子的锅铲声。想买可以叫住他。','{}','vendor.arrived:966dc6357d1c4b7fb3529ceeb99e2275:companion',1795320455.797039032,NULL,NULL,NULL);
INSERT INTO notes VALUES(5,'companion','pocket.given','【厨房·非用户发言】用户给了你 50 零花钱,现在有 50。','用户给了你 50 零花钱,现在有 50。','{}','pocket:companion:grant-1',1795320479.675882101,NULL,NULL,NULL);
INSERT INTO notes VALUES(6,'companion','dishwash.done','【厨房·非用户发言】3 只盘子刷完了。','3 只盘子刷完了。','{}','dishwash:783cd57e1106',1795321079.921666145,NULL,NULL,NULL);
CREATE TABLE recipe_pages (           -- the role's own recipe pages
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  kind TEXT NOT NULL,                  -- fav | adapt | own | menu | code
  ref_id TEXT,                         -- fav: public recipe id; adapt: what it was adapted from
  ref_version INTEGER,
  cur_version INTEGER NOT NULL DEFAULT 1,
  content_id TEXT,                     -- imported code: the same code imported twice is the same page
  src_label TEXT,
  src_by TEXT,
  created_at REAL NOT NULL,
  deleted_at REAL
);
INSERT INTO recipe_pages VALUES('p-42f6ed12','companion','own',NULL,NULL,1,NULL,NULL,NULL,1795319785.711568833,1795320325.746072054);
INSERT INTO recipe_pages VALUES('p-655cd16e','companion','own',NULL,NULL,1,NULL,NULL,NULL,1795319785.714663028,NULL);
INSERT INTO recipe_pages VALUES('p-c76d9ad6','companion','fav','hc-0fd53334',1,1,NULL,NULL,NULL,1795319785.717640877,NULL);
INSERT INTO recipe_pages VALUES('p-f10194d1','companion','own',NULL,NULL,1,NULL,NULL,NULL,1795320479.897338151,1795321079.962070942);
CREATE TABLE recipe_page_versions (   -- every version of every page, never rewritten
  page_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  items_json TEXT NOT NULL DEFAULT '[]',
  optional_json TEXT NOT NULL DEFAULT '[]',
  method TEXT,
  minutes INTEGER,
  note TEXT NOT NULL DEFAULT '',
  menu_json TEXT,
  created_at REAL NOT NULL,
  PRIMARY KEY (page_id, version)
);
INSERT INTO recipe_page_versions VALUES('p-42f6ed12',1,'葱花蛋饼','[{"item": "egg", "qty": 1}, {"item": "scallion", "qty": 1}]','[]','fry',8,'',NULL,1795319785.711568833);
INSERT INTO recipe_page_versions VALUES('p-655cd16e',1,'番茄蛋汤','[{"item": "tomato", "qty": 1}, {"item": "egg", "qty": 1}]','[]','boil',10,'',NULL,1795319785.714663028);
INSERT INTO recipe_page_versions VALUES('p-c76d9ad6',1,'油焖大虾','[{"item": "scallion", "qty": 1}]','[]','boil',40,'',NULL,1795319785.717640877);
INSERT INTO recipe_page_versions VALUES('p-f10194d1',1,'葱香炒蛋','[{"item": "egg", "qty": 1}, {"item": "scallion", "qty": 1}]','[]','stirfry',6,'',NULL,1795320479.897338151);
CREATE TABLE recipe_notes (
  key TEXT PRIMARY KEY, who TEXT NOT NULL, page_id TEXT NOT NULL, session_id TEXT,
  text TEXT NOT NULL, created_at REAL NOT NULL
);
INSERT INTO recipe_notes VALUES('236659c904987f60','companion','p-42f6ed12',NULL,'葱多一点更香',1795320325.738608838);
INSERT INTO recipe_notes VALUES('f7ef0ae7b95320c8','companion','p-f10194d1','7f95c38866c04350ad448ebf329a7e98','下回少放点盐',1795321079.936412812);
CREATE TABLE recipe_orders (          -- the human's orders
  id TEXT PRIMARY KEY, who TEXT NOT NULL, identity TEXT NOT NULL, name TEXT NOT NULL,
  state TEXT NOT NULL,                 -- received | planned | cooking | done | withdrawn
  his_note TEXT NOT NULL DEFAULT '', session_id TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE recipe_firsts (          -- the first time a recipe was eaten (the new-dish bonus)
  who TEXT NOT NULL, identity TEXT NOT NULL, eat_key TEXT NOT NULL, session_id TEXT,
  name TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, PRIMARY KEY (who, identity)
);
INSERT INTO recipe_firsts VALUES('companion','hc-0fd53334','eat:e1121d88743245a8','a7128ce95eb5436ebb15716b67179f6b','油焖大虾',1795319785.681506156);
INSERT INTO recipe_firsts VALUES('companion','p-f10194d1','eat:c46f6038ba4641bc','7f95c38866c04350ad448ebf329a7e98','葱香炒蛋',1795321079.952905894);
CREATE TABLE recipe_buys (
  key TEXT PRIMARY KEY, who TEXT NOT NULL, identity TEXT NOT NULL, items_json TEXT NOT NULL,
  receipt TEXT NOT NULL, at REAL NOT NULL
);
INSERT INTO recipe_buys VALUES('fa6e5273d2719ec4','companion','hc-581cccda','["pork", "woodear", "v_f88cded0", "v_d8496b86"]','照「生汆丸子汤」买好了:猪肉×1、木耳×1、黄花×1、泡好的粉丝×1,放进冰箱了。用掉一张买菜券(还剩 2 张)。',1795318705.404484034);
CREATE TABLE recipe_flags (           -- a recipe with a mistake can be taken out of circulation
  recipe_id TEXT PRIMARY KEY, stopped INTEGER NOT NULL DEFAULT 1, why TEXT NOT NULL DEFAULT '', at REAL NOT NULL
);
CREATE TABLE kitchen_prefs (          -- things the human does not want recommended
  who TEXT NOT NULL, kind TEXT NOT NULL, item TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY (who, kind, item)
);
INSERT INTO kitchen_prefs VALUES('companion','dislike','celery',1795320455.763176919);
INSERT INTO kitchen_prefs VALUES('companion','dislike','eggplant',1795320455.763176919);
CREATE TABLE dish_counts (            -- proficiency, by dish name (free pots and changed recipes)
  who TEXT NOT NULL, dish TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (who, dish)
);
INSERT INTO dish_counts VALUES('companion','土豆煎蛋',1);
INSERT INTO dish_counts VALUES('companion','番茄炒蛋',1);
INSERT INTO dish_counts VALUES('companion','西红柿鸡蛋挂面',1);
CREATE TABLE recipe_counts (          -- proficiency, by recipe (pots that followed it)
  who TEXT NOT NULL, identity TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (who, identity)
);
INSERT INTO recipe_counts VALUES('companion','hc-0fd53334',1);
INSERT INTO recipe_counts VALUES('companion','p-f10194d1',1);
CREATE TABLE cook_settlements (       -- written once when a pot is served, never changed
  session_id TEXT PRIMARY KEY, who TEXT NOT NULL, dish TEXT NOT NULL, method TEXT,
  outcome TEXT NOT NULL, link TEXT NOT NULL, recipe_id TEXT, recipe_version INTEGER,
  book TEXT, book_key TEXT, before_n INTEGER, after_n INTEGER, before_tier TEXT, after_tier TEXT,
  first_time INTEGER NOT NULL DEFAULT 0, mishap_id TEXT, mishap_ver INTEGER, rescued_item TEXT,
  started_at REAL NOT NULL, settled_at REAL NOT NULL
);
INSERT INTO cook_settlements VALUES('5f8202f2be2243169d920060cd4a199f','companion','土豆煎蛋','fry','great','free',NULL,NULL,'dish','土豆煎蛋',0,1,'生疏','生疏',1,NULL,NULL,NULL,1795318085.047755003,1795318445.047755003);
INSERT INTO cook_settlements VALUES('a7128ce95eb5436ebb15716b67179f6b','companion','油焖大虾','boil','great','follow','hc-0fd53334',1,'recipe','hc-0fd53334',0,1,'生疏','生疏',1,NULL,1,NULL,1795318705.625257015,1795319305.625257015);
INSERT INTO cook_settlements VALUES('7668e994743545ef9ed7cd7dd40aa97e','companion','番茄炒蛋','stirfry','great','free',NULL,NULL,'dish','番茄炒蛋',0,1,'生疏','生疏',1,NULL,1,NULL,1795319425.657275915,1795319725.657275915);
INSERT INTO cook_settlements VALUES('7f95c38866c04350ad448ebf329a7e98','companion','葱香炒蛋','stirfry','great','follow','p-f10194d1',1,'recipe','p-f10194d1',0,1,'生疏','生疏',1,'general.13',1,NULL,1795320479.904274941,1795320839.904274941);
INSERT INTO cook_settlements VALUES('f73f2ee0bd5541e29d39d8752527c95b','companion','西红柿鸡蛋挂面','boil','great','changed','hc-27764b15',1,'dish','西红柿鸡蛋挂面',0,1,'生疏','生疏',1,NULL,1,NULL,1795320479.888804197,1795320959.888804197);
CREATE TABLE achievements_earned (    -- earned is kept for good
  who TEXT NOT NULL, ach TEXT NOT NULL, earned_at REAL NOT NULL, evidence TEXT NOT NULL DEFAULT '',
  why TEXT NOT NULL DEFAULT '', PRIMARY KEY (who, ach)
);
INSERT INTO achievements_earned VALUES('companion','own_dish',1795320839.904274941,'7f95c38866c04350ad448ebf329a7e98','照自己记的「葱香炒蛋」做成了。');
CREATE TABLE dex_art (                -- one picture per dish page; redrawing keeps the old ones
  page_key TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, path TEXT NOT NULL DEFAULT '',
  err TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, PRIMARY KEY (page_key, version)
);
CREATE TABLE dex_art_choice (page_key TEXT PRIMARY KEY, version INTEGER NOT NULL, at REAL NOT NULL);
CREATE TABLE dex_notes (who TEXT NOT NULL, page_key TEXT NOT NULL, text TEXT NOT NULL, at REAL NOT NULL,
  PRIMARY KEY (who, page_key));
CREATE TABLE dex_merges (who TEXT NOT NULL, dish TEXT NOT NULL, page_key TEXT NOT NULL, at REAL NOT NULL,
  PRIMARY KEY (who, dish));
CREATE TABLE dishes (                 -- plates: one per meal
  id TEXT PRIMARY KEY, who TEXT NOT NULL, eat_key TEXT NOT NULL UNIQUE, dish TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL,                 -- sink | washing | clean | broken | machine
  job_id TEXT, done_at REAL, created_at REAL NOT NULL
);
INSERT INTO dishes VALUES('c6cfacec2b71','companion','eat:e1121d88743245a8','油焖大虾','clean','783cd57e1106',1795320445.74915409,1795319785.681506156);
INSERT INTO dishes VALUES('f2c44521653d','companion','eat:55895eff411e4c94','番茄炒蛋','clean','783cd57e1106',1795320565.74915409,1795319785.692268133);
INSERT INTO dishes VALUES('d6e016c8c448','companion','eat:5d7fbcbc28cb4611','土豆煎蛋','clean','783cd57e1106',1795320685.74915409,1795319785.702565193);
INSERT INTO dishes VALUES('8522f0dd3052','companion','eat:1e2fa499e54a4e4e','西红柿鸡蛋挂面','washing','c231296afa55',NULL,1795321079.941677093);
INSERT INTO dishes VALUES('3e2c28a29cb9','companion','eat:c46f6038ba4641bc','葱香炒蛋','washing','c231296afa55',NULL,1795321079.952905894);
CREATE TABLE wash_jobs (              -- one washing-up: how many, how long each, which breaks, fixed at the start
  id TEXT PRIMARY KEY, who TEXT NOT NULL, key TEXT NOT NULL UNIQUE, dish_ids_json TEXT NOT NULL, per_s REAL NOT NULL,
  break_idx_json TEXT NOT NULL DEFAULT '[]', started_at REAL NOT NULL, state TEXT NOT NULL, ended_at REAL,
  told INTEGER NOT NULL DEFAULT 0
);
INSERT INTO wash_jobs VALUES('783cd57e1106','companion','4bef262c48f68296','["c6cfacec2b71", "f2c44521653d", "d6e016c8c448"]',120.0,'[]',1795320325.74915409,'done',1795320685.74915409,1);
INSERT INTO wash_jobs VALUES('c231296afa55','companion','425d37a52bd20e40','["8522f0dd3052", "3e2c28a29cb9"]',120.0,'[1]',1795321079.965278864,'running',NULL,0);
CREATE TABLE wash_settings (who TEXT PRIMARY KEY, self_wash INTEGER NOT NULL DEFAULT 0, quota INTEGER,
  updated_at REAL NOT NULL);
INSERT INTO wash_settings VALUES('companion',1,NULL,1795318705.379956961);
CREATE TABLE jars (                   -- the three jars on the sill
  who TEXT NOT NULL, slot INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'empty', item_id TEXT, item_name TEXT,
  freshness TEXT, how TEXT, how_word TEXT, note TEXT NOT NULL DEFAULT '', sealed_at REAL, due_at REAL, seal_key TEXT,
  PRIMARY KEY (who, slot)
);
INSERT INTO jars VALUES('companion',1,'sealed','apple','苹果','fresh','sugar','糖','冬天吃',1795321139.976977826,1795580339.976977826,'6fe0a94d7e9178bd');
INSERT INTO jars VALUES('companion',2,'empty',NULL,NULL,NULL,NULL,NULL,'',NULL,NULL,NULL);
INSERT INTO jars VALUES('companion',3,'empty',NULL,NULL,NULL,NULL,NULL,'',NULL,NULL,NULL);
CREATE TABLE jar_goods (
  id TEXT PRIMARY KEY, who TEXT NOT NULL, name TEXT NOT NULL, item_name TEXT NOT NULL, ok INTEGER NOT NULL,
  total INTEGER NOT NULL, left_n INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', opened_at REAL NOT NULL,
  told INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE jar_takes (
  take_key TEXT PRIMARY KEY, who TEXT NOT NULL, goods_id TEXT NOT NULL, day TEXT NOT NULL, by_who TEXT NOT NULL,
  receipt TEXT NOT NULL, at REAL NOT NULL
);
CREATE TABLE jar_caps (who TEXT PRIMARY KEY, cap INTEGER NOT NULL);
CREATE TABLE vendor_days (day TEXT PRIMARY KEY, plan_json TEXT NOT NULL, weather TEXT NOT NULL DEFAULT '',
  made_at REAL NOT NULL);
INSERT INTO vendor_days VALUES('2026-11-22','[{"slot": 0, "vendor": "popcorn", "arrive_at": 1795334667.6880472}]','',1795318105.144881963);
CREATE TABLE vendor_visits (
  id TEXT PRIMARY KEY, day TEXT NOT NULL, slot INTEGER NOT NULL, vendor TEXT NOT NULL,
  arrive_at REAL NOT NULL, leave_at REAL NOT NULL, goods_json TEXT NOT NULL, told TEXT NOT NULL DEFAULT '[]',
  created_at REAL NOT NULL, UNIQUE(day, slot)
);
INSERT INTO vendor_visits VALUES('966dc6357d1c4b7fb3529ceeb99e2275','2026-11-22',0,'chestnut',1795320455.782500029,1795322855.782500029,'[{"id": "roast_chestnut", "name": "糖炒栗子", "kind": "snack", "unit": "袋", "price": 7, "stock": 6, "satiety": 8.0, "energy": 0.03, "aliases": ["炒栗子"]}, {"id": "chestnut", "name": "栗子", "kind": "ingredient", "unit": "份", "price": 10, "stock": 2, "ingredient": "v_e7da2de3", "note": "栗子 — 和鸡腿一起炖,四十分钟。", "aliases": []}]','["companion"]',1795320455.782500029);
CREATE TABLE vendor_orders (
  id TEXT PRIMARY KEY, who TEXT NOT NULL, visit_id TEXT NOT NULL, vendor TEXT NOT NULL,
  item_id TEXT NOT NULL, item_name TEXT NOT NULL, kind TEXT NOT NULL, unit TEXT NOT NULL,
  qty INTEGER NOT NULL, unit_price INTEGER NOT NULL, total INTEGER NOT NULL,
  payer TEXT NOT NULL, day TEXT NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', balance INTEGER,
  deliver_tries INTEGER NOT NULL DEFAULT 0, receipt_extra TEXT NOT NULL DEFAULT '[]',
  debit_unsure INTEGER NOT NULL DEFAULT 0, told INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, updated_at REAL NOT NULL
);
INSERT INTO vendor_orders VALUES('bc0f56756d27f5400a87','companion','966dc6357d1c4b7fb3529ceeb99e2275','chestnut','roast_chestnut','糖炒栗子','snack','袋',1,7,7,'self','2026-11-22','debit_failed','broke',0,0,'[]',0,1,1795320455.79199791,1795320455.794034004);
INSERT INTO vendor_orders VALUES('95545f096075a0ca29ff','companion','966dc6357d1c4b7fb3529ceeb99e2275','chestnut','roast_chestnut','糖炒栗子','snack','袋',1,7,7,'self','2026-11-22','delivered','',43,0,'[]',0,1,1795321139.981926918,1795321139.981926918);
CREATE TABLE vendor_regulars (who TEXT NOT NULL, vendor TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
  last_items TEXT NOT NULL DEFAULT '', last_at REAL, PRIMARY KEY (who, vendor));
INSERT INTO vendor_regulars VALUES('companion','chestnut',1,'糖炒栗子',1795321139.981926918);
CREATE TABLE vendor_gifts (order_id TEXT PRIMARY KEY, who TEXT NOT NULL, item_id TEXT NOT NULL,
  text TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE vendor_talks (visit_id TEXT NOT NULL, who TEXT NOT NULL, history_json TEXT NOT NULL DEFAULT '[]',
  n INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL, PRIMARY KEY (visit_id, who));
INSERT INTO vendor_talks VALUES('966dc6357d1c4b7fb3529ceeb99e2275','companion','[{"his": "今天有什么好吃的", "shown": "现炒的,闻见香了吧。"}]',1,1795320455.787512064);
CREATE TABLE vendor_talk_lines (msg_key TEXT PRIMARY KEY, visit_id TEXT NOT NULL, who TEXT NOT NULL,
  nth INTEGER NOT NULL, his TEXT NOT NULL, shown TEXT NOT NULL, from_model INTEGER NOT NULL, receipt TEXT NOT NULL,
  at REAL NOT NULL);
INSERT INTO vendor_talk_lines VALUES('065082c13ecddbf9','966dc6357d1c4b7fb3529ceeb99e2275','companion',1,'今天有什么好吃的','现炒的,闻见香了吧。',0,unistr('糖炒栗子 7 一袋(还有 6 袋),栗子 10 一份(还有 2 份)。\u000a小贩说:「现炒的,闻见香了吧。」'),1795320455.787512064);
CREATE TABLE vendor_flowers (id TEXT PRIMARY KEY, who TEXT NOT NULL, order_id TEXT NOT NULL UNIQUE,
  variety TEXT NOT NULL, name TEXT NOT NULL, bought_at REAL NOT NULL, removed_at REAL, gifted_at REAL, gift_note TEXT);
CREATE TABLE vendor_flower_requests (id TEXT PRIMARY KEY, who TEXT NOT NULL, name TEXT NOT NULL,
  msg_key TEXT NOT NULL UNIQUE, state TEXT NOT NULL, created_at REAL NOT NULL, decided_at REAL);
CREATE TABLE wallet_local (           -- the built-in pocket-money ledger (when no wallet is configured)
  id TEXT PRIMARY KEY, who TEXT NOT NULL, kind TEXT NOT NULL,   -- grant | vendor
  amount INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active', at REAL NOT NULL
);
INSERT INTO wallet_local VALUES('grant:grant-1','companion','grant',50,'','active',1795320479.675487996);
INSERT INTO wallet_local VALUES('vendor:95545f096075a0ca29ff','companion','vendor',7,'vendor 糖炒栗子×1','active',1795321139.983993054);
INSERT INTO sqlite_sequence VALUES('fridge_log',9);
INSERT INTO sqlite_sequence VALUES('notes',6);
INSERT INTO sqlite_sequence VALUES('stamina_log',17);
CREATE INDEX idx_batches_who ON batches(who, item_id, bought_at);
CREATE INDEX idx_fridge_log_who ON fridge_log(who, at);
CREATE INDEX idx_cook_sessions_who_status ON cook_sessions(who, status, started_at);
CREATE INDEX idx_potions_who ON potions(who, state);
CREATE INDEX idx_snack_log_day ON snack_log(who, day, snack);
CREATE INDEX idx_menu_for ON menu(for_who, eaten_at);
CREATE INDEX idx_meals_who ON meals(who, at);
CREATE INDEX idx_notes_who ON notes(who, taken_at);
CREATE INDEX idx_recipe_pages_who ON recipe_pages(who, kind, deleted_at);
CREATE INDEX idx_recipe_orders ON recipe_orders(who, identity, state, created_at);
CREATE INDEX idx_cook_settlements_who ON cook_settlements(who, settled_at);
CREATE INDEX idx_dishes_who ON dishes(who, state, created_at);
CREATE UNIQUE INDEX uq_wash_jobs_running ON wash_jobs(who) WHERE state='running';
CREATE INDEX idx_jar_goods_who ON jar_goods(who, name, opened_at);
CREATE INDEX idx_jar_takes_day ON jar_takes(who, day);
CREATE INDEX idx_vendor_visits_time ON vendor_visits(arrive_at, leave_at);
CREATE INDEX idx_vendor_orders_state ON vendor_orders(state);
CREATE INDEX idx_vendor_orders_quota ON vendor_orders(who, payer, day);
CREATE INDEX idx_vendor_flowers_who ON vendor_flowers(who, bought_at);
COMMIT;
