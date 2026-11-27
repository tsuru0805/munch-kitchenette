-- A kitchen database as munch-kitchenette 0.2.1 left it (`sqlite3 kitchenette.db .dump`), for
-- tests/test_upgrade_from_021.py. Made by running 0.2.1 itself (`kitchenette serve`, fast-forward clock on,
-- role "companion", only the jars switched on, spoiled food kept in the fridge, markers through /api/inline):
-- a spoiled apple sealed with 糖 (opened, thrown away), a carrot sealed with 盐 and the slip 配粥 (opened as
-- 腌胡萝卜, one serving taken), and three jars still sealed when 0.2.1 stopped: an apple with 冰糖 and the slip
-- 冬天吃, a lemon with 蜂蜜, and a spoiled apple with 蜂蜜 and the slip 试试看.
-- 0.2.1 stored no name for a sealed jar; 0.2.2 names them when they open, by the rule they were sealed under.
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
INSERT INTO batches VALUES('a934948649414eb7bf5fdaa34c074ff6','companion','carrot',1,1796441309.228046178,'her','her',NULL,NULL);
CREATE TABLE coupons (
  who TEXT PRIMARY KEY,
  count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE once_keys (
  key TEXT PRIMARY KEY,
  at REAL NOT NULL,
  result TEXT NOT NULL DEFAULT ''
);
INSERT INTO once_keys VALUES('worm_since',1795750093.76968193,'');
INSERT INTO once_keys VALUES('fruit_worm_since',1795750093.76968193,'');
INSERT INTO once_keys VALUES('play_since',1795750704.281270027,'');
INSERT INTO once_keys VALUES('flag:inline_seen',1796441309.211343051,'');
INSERT INTO once_keys VALUES('jar_seal:363143e57bd631f6',1796441309.214306116,'封上了:苹果、糖。12 月 8 日中午好。');
INSERT INTO once_keys VALUES('inline:363143e57bd631f6',1796441309.215061903,'{"marker": "封罐", "args": "苹果 糖", "ok": true, "text": "封上了:苹果、糖。12 月 8 日中午好。", "rendered": "刚才正文里那条『封罐』:封上了:苹果、糖。12 月 8 日中午好。", "attachments": []}');
INSERT INTO once_keys VALUES('jar_seal:9f06ca02a0a67ee7',1796441309.237477065,'封上了:胡萝卜、盐。明天中午好。纸条:「配粥」');
INSERT INTO once_keys VALUES('inline:9f06ca02a0a67ee7',1796441309.238224983,'{"marker": "封罐", "args": "胡萝卜 盐 | 配粥", "ok": true, "text": "封上了:胡萝卜、盐。明天中午好。纸条:「配粥」", "rendered": "刚才正文里那条『封罐』:封上了:胡萝卜、盐。明天中午好。纸条:「配粥」", "attachments": []}');
INSERT INTO once_keys VALUES('note:jar:g-3f1a6d91d7',1796527709.874464035,'');
INSERT INTO once_keys VALUES('fill:jar:jar:04bfc79f84f6a96e',1796527829.891389847,'');
INSERT INTO once_keys VALUES('inline:04bfc79f84f6a96e',1796527829.892350913,'{"marker": "零食", "args": "腌胡萝卜", "ok": true, "text": "吃了一份腌胡萝卜。封罐时的纸条:「配粥」", "rendered": "刚才正文里那条『零食』:吃了一份腌胡萝卜。封罐时的纸条:「配粥」", "attachments": []}');
INSERT INTO once_keys VALUES('note:jar:g-336820a453',1796700631.144538164,'');
INSERT INTO once_keys VALUES('jar_seal:63a5708dfcdd28cb',1796700751.168066979,'封上了:苹果、冰糖。12 月 11 日中午好。纸条:「冬天吃」');
INSERT INTO once_keys VALUES('inline:63a5708dfcdd28cb',1796700751.16887188,'{"marker": "封罐", "args": "苹果 冰糖 | 冬天吃", "ok": true, "text": "封上了:苹果、冰糖。12 月 11 日中午好。纸条:「冬天吃」", "rendered": "刚才正文里那条『封罐』:封上了:苹果、冰糖。12 月 11 日中午好。纸条:「冬天吃」", "attachments": []}');
INSERT INTO once_keys VALUES('jar_seal:3bdd75cc9ce0066b',1796700751.184702874,'封上了:柠檬、蜂蜜。后天中午好。');
INSERT INTO once_keys VALUES('inline:3bdd75cc9ce0066b',1796700751.185471057,'{"marker": "封罐", "args": "柠檬 蜂蜜", "ok": true, "text": "封上了:柠檬、蜂蜜。后天中午好。", "rendered": "刚才正文里那条『封罐』:封上了:柠檬、蜂蜜。后天中午好。", "attachments": []}');
INSERT INTO once_keys VALUES('fill:eat:ddbbaf1ed53849b9',1796700758.609313012,'');
INSERT INTO once_keys VALUES('inline:ddbbaf1ed53849b9',1796700758.612909078,'{"marker": "吃", "args": "苹果", "ok": true, "text": "🍚 吃好了：苹果。距上次：这是第一餐 / 今日第 1 餐 / 本周 1 餐\n饱食度：0% → 15%（饿过头了）\n从冰箱拿了苹果直接吃了(还剩 1 个)。", "rendered": "刚才正文里那条『吃』:🍚 吃好了：苹果。距上次：这是第一餐 / 今日第 1 餐 / 本周 1 餐\n饱食度：0% → 15%（饿过头了）\n从冰箱拿了苹果直接吃了(还剩 1 个)。", "attachments": []}');
INSERT INTO once_keys VALUES('jar_seal:db0a1a0877956f8f',1796700765.322828054,'封上了:苹果、蜂蜜。12 月 11 日中午好。纸条:「试试看」');
INSERT INTO once_keys VALUES('inline:db0a1a0877956f8f',1796700765.323967934,'{"marker": "封罐", "args": "苹果 蜂蜜 | 试试看", "ok": true, "text": "封上了:苹果、蜂蜜。12 月 11 日中午好。纸条:「试试看」", "rendered": "刚才正文里那条『封罐』:封上了:苹果、蜂蜜。12 月 11 日中午好。纸条:「试试看」", "attachments": []}');
CREATE TABLE fridge_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  who TEXT NOT NULL,
  at REAL NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL
);
INSERT INTO fridge_log VALUES(1,'companion',1795750104.270302057,'bought','用户买了苹果×2');
INSERT INTO fridge_log VALUES(2,'companion',1796354908.573677062,'wormed','冰箱里的苹果坏了,长虫了');
INSERT INTO fridge_log VALUES(3,'companion',1796441309.21308589,'jar_sealed','把苹果封进了窗台的罐子');
INSERT INTO fridge_log VALUES(4,'companion',1796441309.228046178,'bought','用户买了胡萝卜×2');
INSERT INTO fridge_log VALUES(5,'companion',1796441309.236925841,'jar_sealed','把胡萝卜封进了窗台的罐子');
INSERT INTO fridge_log VALUES(6,'companion',1796700751.158882141,'bought','用户买了苹果×2、柠檬×1');
INSERT INTO fridge_log VALUES(7,'companion',1796700751.167592048,'jar_sealed','把苹果封进了窗台的罐子');
INSERT INTO fridge_log VALUES(8,'companion',1796700751.184223891,'jar_sealed','把柠檬封进了窗台的罐子');
INSERT INTO fridge_log VALUES(9,'companion',1796700758.604359866,'ate_raw','从冰箱拿了苹果直接吃了');
INSERT INTO fridge_log VALUES(10,'companion',1796700765.322037936,'jar_sealed','把苹果封进了窗台的罐子');
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
INSERT INTO appetite VALUES('companion',15.0,1796700758.604359866,NULL,NULL,NULL,1,1);
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
CREATE TABLE worm_pending (
  who TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  dish TEXT NOT NULL,
  made_at REAL NOT NULL,
  at REAL NOT NULL,
  snack TEXT NOT NULL DEFAULT 'pudding',
  source TEXT NOT NULL DEFAULT 'dish'
);
INSERT INTO worm_pending VALUES('companion','492c4e8c63fa4b1d92c4a7399c27dc2d','苹果',1795750104.270302057,1796354908.573677062,'chocolate','fruit');
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
CREATE TABLE meals (
  id TEXT PRIMARY KEY,
  who TEXT NOT NULL,
  meal TEXT NOT NULL,
  note TEXT,
  at REAL NOT NULL
);
INSERT INTO meals VALUES('ac5ffa2287d347688307d300f75540fe','companion','苹果',NULL,1796700758.604359866);
CREATE TABLE stamina (
  who TEXT PRIMARY KEY,
  value REAL NOT NULL,
  updated_at REAL NOT NULL,
  round_at REAL,                            -- when the current run of tool calls began
  round_kinds TEXT NOT NULL DEFAULT '[]',   -- kinds of work already charged in it
  round_cost REAL NOT NULL DEFAULT 0
);
INSERT INTO stamina VALUES('companion',0.925262082349368353,1796700758.61149788,NULL,'[]',0.0);
CREATE TABLE stamina_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  who TEXT NOT NULL,
  at REAL NOT NULL,
  delta REAL NOT NULL,
  value REAL NOT NULL,
  rule TEXT NOT NULL DEFAULT ''
);
INSERT INTO stamina_log VALUES(1,'companion',1796527829.890679121,0.02000000000000000041,0.7199999999999999734,'jar');
INSERT INTO stamina_log VALUES(2,'companion',1796700758.604359866,-0.05000000000000000277,0.8252620627294051658,'kitchen:raw');
INSERT INTO stamina_log VALUES(3,'companion',1796700758.61149788,0.1000000000000000055,0.925262082349368353,'rest');
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
, claim_token TEXT, claim_at REAL);
INSERT INTO notes VALUES(1,'companion','fridge.bought','用户给你买了菜,放进冰箱了:苹果×2、胡萝卜×2、苹果×2、柠檬×1。','用户给你买了菜,放进冰箱了:苹果×2、胡萝卜×2、苹果×2、柠檬×1。','{"items": "苹果×2、柠檬×1", "events": [{"items": "苹果×2"}, {"items": "胡萝卜×2"}, {"items": "苹果×2、柠檬×1"}]}',NULL,1795750104.27199483,NULL,NULL,NULL,NULL,NULL);
INSERT INTO notes VALUES(2,'companion','hungry','【厨房·非用户发言】你有点饿了(饱食度低于 30%)。冰箱里有:苹果×2。','【厨房·非用户发言】你有点饿了(饱食度低于 30%)。冰箱里有:苹果×2。','{}',NULL,1795762704.37399602,NULL,NULL,NULL,NULL,NULL);
INSERT INTO notes VALUES(3,'companion','jar.opened','【厨房·非用户发言】窗台上的腌胡萝卜泡好了,收进零食架了(3 份)。','窗台上的腌胡萝卜泡好了,收进零食架了(3 份)。','{}','jar:g-3f1a6d91d7',1796527709.874464035,NULL,NULL,NULL,NULL,NULL);
INSERT INTO notes VALUES(4,'companion','jar.opened','【厨房·非用户发言】窗台上那罐苹果开出来是坏的(封进去的时候就坏了),整罐扔了,罐子洗干净空出来了。','窗台上那罐苹果开出来是坏的(封进去的时候就坏了),整罐扔了,罐子洗干净空出来了。','{}','jar:g-336820a453',1796700631.144538164,NULL,NULL,NULL,NULL,NULL);
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
CREATE TABLE recipe_notes (
  key TEXT PRIMARY KEY, who TEXT NOT NULL, page_id TEXT NOT NULL, session_id TEXT,
  text TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE recipe_orders (          -- the human's orders
  id TEXT PRIMARY KEY, who TEXT NOT NULL, identity TEXT NOT NULL, name TEXT NOT NULL,
  state TEXT NOT NULL,                 -- received | planned | cooking | done | withdrawn
  his_note TEXT NOT NULL DEFAULT '', session_id TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE recipe_firsts (          -- the first time a recipe was eaten (the new-dish bonus)
  who TEXT NOT NULL, identity TEXT NOT NULL, eat_key TEXT NOT NULL, session_id TEXT,
  name TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, PRIMARY KEY (who, identity)
);
CREATE TABLE recipe_buys (
  key TEXT PRIMARY KEY, who TEXT NOT NULL, identity TEXT NOT NULL, items_json TEXT NOT NULL,
  receipt TEXT NOT NULL, at REAL NOT NULL
);
CREATE TABLE recipe_flags (           -- a recipe with a mistake can be taken out of circulation
  recipe_id TEXT PRIMARY KEY, stopped INTEGER NOT NULL DEFAULT 1, why TEXT NOT NULL DEFAULT '', at REAL NOT NULL
);
CREATE TABLE kitchen_prefs (          -- things the human does not want recommended
  who TEXT NOT NULL, kind TEXT NOT NULL, item TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY (who, kind, item)
);
CREATE TABLE dish_counts (            -- proficiency, by dish name (free pots and changed recipes)
  who TEXT NOT NULL, dish TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (who, dish)
);
CREATE TABLE recipe_counts (          -- proficiency, by recipe (pots that followed it)
  who TEXT NOT NULL, identity TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (who, identity)
);
CREATE TABLE cook_settlements (       -- written once when a pot is served, never changed
  session_id TEXT PRIMARY KEY, who TEXT NOT NULL, dish TEXT NOT NULL, method TEXT,
  outcome TEXT NOT NULL, link TEXT NOT NULL, recipe_id TEXT, recipe_version INTEGER,
  book TEXT, book_key TEXT, before_n INTEGER, after_n INTEGER, before_tier TEXT, after_tier TEXT,
  first_time INTEGER NOT NULL DEFAULT 0, mishap_id TEXT, mishap_ver INTEGER, rescued_item TEXT,
  started_at REAL NOT NULL, settled_at REAL NOT NULL
);
CREATE TABLE achievements_earned (    -- earned is kept for good
  who TEXT NOT NULL, ach TEXT NOT NULL, earned_at REAL NOT NULL, evidence TEXT NOT NULL DEFAULT '',
  why TEXT NOT NULL DEFAULT '', PRIMARY KEY (who, ach)
);
INSERT INTO achievements_earned VALUES('companion','first_jar',1796527709.236925841,'','窗台上的腌胡萝卜泡好了。');
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
CREATE TABLE wash_jobs (              -- one washing-up: how many, how long each, which breaks, fixed at the start
  id TEXT PRIMARY KEY, who TEXT NOT NULL, key TEXT NOT NULL UNIQUE, dish_ids_json TEXT NOT NULL, per_s REAL NOT NULL,
  break_idx_json TEXT NOT NULL DEFAULT '[]', started_at REAL NOT NULL, state TEXT NOT NULL, ended_at REAL,
  told INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE wash_settings (who TEXT PRIMARY KEY, self_wash INTEGER NOT NULL DEFAULT 0, quota INTEGER,
  updated_at REAL NOT NULL);
CREATE TABLE jars (                   -- the three jars on the sill
  who TEXT NOT NULL, slot INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'empty', item_id TEXT, item_name TEXT,
  freshness TEXT, how TEXT, how_word TEXT, note TEXT NOT NULL DEFAULT '', sealed_at REAL, due_at REAL, seal_key TEXT,
  PRIMARY KEY (who, slot)
);
INSERT INTO jars VALUES('companion',1,'sealed','apple','苹果','fresh','sugar','冰糖','冬天吃',1796700751.167592048,1796959951.167592048,'63a5708dfcdd28cb');
INSERT INTO jars VALUES('companion',2,'sealed','lemon','柠檬','fresh','honey','蜂蜜','',1796700751.184223891,1796873551.184223891,'3bdd75cc9ce0066b');
INSERT INTO jars VALUES('companion',3,'sealed','apple','苹果','bad','honey','蜂蜜','试试看',1796700765.322037936,1796959965.322037936,'db0a1a0877956f8f');
CREATE TABLE jar_goods (
  id TEXT PRIMARY KEY, who TEXT NOT NULL, name TEXT NOT NULL, item_name TEXT NOT NULL, ok INTEGER NOT NULL,
  total INTEGER NOT NULL, left_n INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', opened_at REAL NOT NULL,
  told INTEGER NOT NULL DEFAULT 0
);
INSERT INTO jar_goods VALUES('g-3f1a6d91d7','companion','腌胡萝卜','胡萝卜',1,3,2,'配粥',1796527709.236925841,1);
INSERT INTO jar_goods VALUES('g-336820a453','companion','苹果','苹果',0,0,0,'',1796700509.21308589,1);
CREATE TABLE jar_takes (
  take_key TEXT PRIMARY KEY, who TEXT NOT NULL, goods_id TEXT NOT NULL, day TEXT NOT NULL, by_who TEXT NOT NULL,
  receipt TEXT NOT NULL, at REAL NOT NULL
);
INSERT INTO jar_takes VALUES('jar:04bfc79f84f6a96e','companion','g-3f1a6d91d7','2026-12-06','self','吃了一份腌胡萝卜。封罐时的纸条:「配粥」',1796527829.890679121);
CREATE TABLE jar_caps (who TEXT PRIMARY KEY, cap INTEGER NOT NULL);
CREATE TABLE vendor_days (day TEXT PRIMARY KEY, plan_json TEXT NOT NULL, weather TEXT NOT NULL DEFAULT '',
  made_at REAL NOT NULL);
CREATE TABLE vendor_visits (
  id TEXT PRIMARY KEY, day TEXT NOT NULL, slot INTEGER NOT NULL, vendor TEXT NOT NULL,
  arrive_at REAL NOT NULL, leave_at REAL NOT NULL, goods_json TEXT NOT NULL, told TEXT NOT NULL DEFAULT '[]',
  created_at REAL NOT NULL, UNIQUE(day, slot)
);
CREATE TABLE vendor_orders (
  id TEXT PRIMARY KEY, who TEXT NOT NULL, visit_id TEXT NOT NULL, vendor TEXT NOT NULL,
  item_id TEXT NOT NULL, item_name TEXT NOT NULL, kind TEXT NOT NULL, unit TEXT NOT NULL,
  qty INTEGER NOT NULL, unit_price INTEGER NOT NULL, total INTEGER NOT NULL,
  payer TEXT NOT NULL, day TEXT NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', balance INTEGER,
  deliver_tries INTEGER NOT NULL DEFAULT 0, receipt_extra TEXT NOT NULL DEFAULT '[]',
  debit_unsure INTEGER NOT NULL DEFAULT 0, told INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE vendor_regulars (who TEXT NOT NULL, vendor TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
  last_items TEXT NOT NULL DEFAULT '', last_at REAL, PRIMARY KEY (who, vendor));
CREATE TABLE vendor_gifts (order_id TEXT PRIMARY KEY, who TEXT NOT NULL, item_id TEXT NOT NULL,
  text TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE vendor_talks (visit_id TEXT NOT NULL, who TEXT NOT NULL, history_json TEXT NOT NULL DEFAULT '[]',
  n INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL, PRIMARY KEY (visit_id, who));
CREATE TABLE vendor_talk_lines (msg_key TEXT PRIMARY KEY, visit_id TEXT NOT NULL, who TEXT NOT NULL,
  nth INTEGER NOT NULL, his TEXT NOT NULL, shown TEXT NOT NULL, from_model INTEGER NOT NULL, receipt TEXT NOT NULL,
  at REAL NOT NULL);
CREATE TABLE vendor_flowers (id TEXT PRIMARY KEY, who TEXT NOT NULL, order_id TEXT NOT NULL UNIQUE,
  variety TEXT NOT NULL, name TEXT NOT NULL, bought_at REAL NOT NULL, removed_at REAL, gifted_at REAL, gift_note TEXT);
CREATE TABLE vendor_flower_requests (id TEXT PRIMARY KEY, who TEXT NOT NULL, name TEXT NOT NULL,
  msg_key TEXT NOT NULL UNIQUE, state TEXT NOT NULL, created_at REAL NOT NULL, decided_at REAL);
CREATE TABLE wallet_local (           -- the built-in pocket-money ledger (when no wallet is configured)
  id TEXT PRIMARY KEY, who TEXT NOT NULL, kind TEXT NOT NULL,   -- grant | vendor
  amount INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active', at REAL NOT NULL
);
INSERT INTO sqlite_sequence VALUES('fridge_log',10);
INSERT INTO sqlite_sequence VALUES('notes',4);
INSERT INTO sqlite_sequence VALUES('stamina_log',3);
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
