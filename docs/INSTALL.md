# Install and run

You need Python 3.11 or newer (the package declares `>=3.11`; it has been
tested on Python 3.14 only). Nothing else: the data lives in one SQLite file.

## Five minutes, from an empty directory

```sh
# 1. get the code
git clone <this repository> munch-kitchenette
cd munch-kitchenette

# 2. an environment of its own
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. install
pip install .

# 4. run
kitchenette serve
```

The server is now on `http://127.0.0.1:8765`:

- `http://127.0.0.1:8765/api/...` is the REST side, for a kitchen page;
- `http://127.0.0.1:8765/mcp` is the MCP side, for your model.

Check it:

```sh
curl http://127.0.0.1:8765/api/health
# {"ok":true,"version":"0.2.0","now":...}
```

Put something in the fridge and look at it the way the model will:

```sh
curl -X POST http://127.0.0.1:8765/api/fridge/buy \
     -H 'content-type: application/json' -d '{"items": ["egg", "tomato"]}'

python examples/mcp_client.py                       # lists the tools, opens a pot, shows the kitchen
```

A file `kitchenette.db` appears in the directory you started the server from.
That file is the whole state. Back it up, move it, delete it to start over.

## Settings

Everything works with no settings at all. To change something, copy
`examples/kitchenette.toml` to `./kitchenette.toml` and edit, or pass
`--config path/to/file.toml`. `kitchenette check` prints every setting and its
current value, written the same way as the file. See [CONFIG.md](CONFIG.md).

A value the kitchen cannot use (a word where a number goes, a misspelt time
zone, a section written twice) stops `kitchenette serve` and `kitchenette
check` right away, with two lines saying which file, which setting and what
belongs there:

```
kitchenette.toml: [fridge] coupon_max = "五": expected a whole number (no quotes)
kitchenette.toml：[fridge] coupon_max 填的是 "五"：要填一个整数，不加引号
```

Four things most people set first:

```toml
[server]
timezone = "Europe/Berlin"   # default: this machine's local time
token = "a-long-random-string"   # required as "Authorization: Bearer ..." once set

[roles]
default = "mika"             # the name of your companion

[words]
human_name = "阿青"           # how the kitchen's sentences refer to you

# what earns a grocery coupon: nothing does until you say so
[coupons]
earn_hint = "写成一篇日记"
[coupons.earn]
write_diary = "日记"         # your companion's tool name = what it made
```

The last one matters: out of the box your companion can only get coupons
from you. Name the tools of its that should earn one (see
`examples/coupons.toml` and [CONFIG.md](CONFIG.md)), or keep handing them out
from the page.

About bracket lines such as `[吃 菜名]`: there is nothing to decide up front.
The default is automatic. Until your chat program really sends a reply to
`/api/inline`, the kitchen's sentences point the model at the tools; once the
first reply arrives they switch to teaching it the bracket lines, by
themselves. See "Bracket markers" in [CONNECT.md](CONNECT.md) if you want to
pin it one way.

```toml
[inline]
enabled = "auto"             # the default; true = always bracket lines, false = always tools
```

Any setting can also come from the environment, named
`KITCHENETTE_<SECTION>_<KEY>`:

```sh
KITCHENETTE_SERVER_PORT=9000 KITCHENETTE_SERVER_TOKEN=... kitchenette serve
```

## Reaching it from elsewhere

The server listens on `127.0.0.1` only. A model client that runs on another
machine (a hosted chat app, for example) needs a public HTTPS address: put a
tunnel or a reverse proxy in front, set `server.token`, and give the client
`https://your-address/mcp` with the token as a bearer header. To listen on all
interfaces directly, set `server.host = "0.0.0.0"`, and do set a token.

## See the whole thing happen

One command, and days pass in seconds:

```sh
python examples/walkthrough.py
```

It starts a kitchen of its own for the occasion (a temporary database, a free
port), then buys, cooks, waits, eats, lets food spoil, lets leftovers grow
worms and throws them out, printing every sentence the model would read,
refusals included. When it is done the temporary kitchen is deleted. Your own
`kitchenette.db` and any server you have running are not touched.

**About the fast-forward clock** (`server.dev_clock`, used by that script on
its own server): it moves the clock of the whole server. Every role in that
database jumps ahead together, food spoils and satiety drops for all of them.
Never switch it on for a kitchen that is in use.

## Develop

```sh
pip install -e '.[dev]'
pytest
```

The tests never touch your `kitchenette.db`: each one runs against a database
file in a temporary directory.

---

# 中文：安装与运行

需要 Python 3.11 或更新的版本（包里声明的是 `>=3.11`，实际只在 Python 3.14 上测试过）。除此之外什么都不用装：所有数据存在一个 SQLite 文件里。

## 五分钟，从一个空文件夹开始

```sh
# 1. 把代码拿下来
git clone <本仓库地址> munch-kitchenette
cd munch-kitchenette

# 2. 给它一个独立的环境
python3 -m venv .venv
source .venv/bin/activate          # Windows 用: .venv\Scripts\activate

# 3. 安装
pip install .

# 4. 启动
kitchenette serve
```

服务现在开在 `http://127.0.0.1:8765`：

- `http://127.0.0.1:8765/api/...` 给厨房页面用；
- `http://127.0.0.1:8765/mcp` 给模型用（MCP）。

确认它活着：

```sh
curl http://127.0.0.1:8765/api/health
# {"ok":true,"version":"0.2.0","now":...}
```

往冰箱里放点东西，再用模型的视角看一眼厨房：

```sh
curl -X POST http://127.0.0.1:8765/api/fridge/buy \
     -H 'content-type: application/json' -d '{"items": ["egg", "tomato"]}'

python examples/mcp_client.py       # 列出工具、开一锅、看厨房
```

启动服务的那个文件夹里会多出一个 `kitchenette.db`。全部状态都在这一个文件里：想备份就复制它，想搬家就带走它，想从头来就删掉它。

## 设置

什么都不设也能跑。想改东西，把 `examples/kitchenette.toml` 复制成当前文件夹下的 `kitchenette.toml` 再改，或者启动时写 `--config 某个文件.toml`。`kitchenette check` 会把每一项设置和它现在的值打印出来，写法和文件里一样。每一项的意思见 [CONFIG.md](CONFIG.md)。

填了厨房用不了的值（该填数字的地方填了字、时区名拼错、同一个段写了两次），`kitchenette serve` 和 `kitchenette check` 会当场停下，用两行话告诉你是哪个文件、哪一项、应该填什么：

```
kitchenette.toml: [fridge] coupon_max = "五": expected a whole number (no quotes)
kitchenette.toml：[fridge] coupon_max 填的是 "五"：要填一个整数，不加引号
```

大多数人最先改的四样：

```toml
[server]
timezone = "Asia/Shanghai"       # 不写就用这台电脑的时区
token = "一长串别人猜不到的字符"    # 设了之后，访问必须带 "Authorization: Bearer ..."

[roles]
default = "mika"                 # 你的小机叫什么

[words]
human_name = "阿青"               # 厨房说话时怎么称呼你

# 做什么能换买菜券：不写就什么都换不了
[coupons]
earn_hint = "写成一篇日记"
[coupons.earn]
write_diary = "日记"             # 你的小机的工具名 = 做出来的是什么
```

最后一样别漏：开箱时他只能从你这里拿到买菜券。把他那些「做了就该得一张」的工具写上（见 `examples/coupons.toml` 和 [CONFIG.md](CONFIG.md)），或者就一直由你在页面上发券。

关于 `[吃 菜名]` 这样的方括号标签：不用事先决定。缺省是自动的——在你的聊天程序真的把回复送进 `/api/inline` 之前，厨房的提示语指向工具；接好之后送进来第一条，它自己就换成教他写标签。想固定成某一种，见 [CONNECT.md](CONNECT.md) 的「方括号标签」。

```toml
[inline]
enabled = "auto"                 # 缺省就是它；true = 一直教他写标签，false = 一直指向工具
```

任何一项设置也可以用环境变量给，名字是 `KITCHENETTE_<段名>_<键名>`：

```sh
KITCHENETTE_SERVER_PORT=9000 KITCHENETTE_SERVER_TOKEN=... kitchenette serve
```

## 从别的地方连它

服务默认只听本机（`127.0.0.1`）。如果模型的客户端不在这台电脑上（比如网页版聊天应用），它需要一个公网的 HTTPS 地址：在前面架一条隧道或反向代理，设好 `server.token`，把 `https://你的地址/mcp` 和 token 填给客户端。想直接对外监听就设 `server.host = "0.0.0.0"`，这时一定要设 token。

## 把整条链看一遍

一条命令，几秒钟看完好几天：

```sh
python examples/walkthrough.py
```

它会自己临时起一间厨房（临时的库、空闲的端口），然后买菜、开锅、等出锅、吃、放到变坏、让剩菜长虫、再扔掉，把模型会读到的每一句话都打印出来，连被拒绝的那些也在内。走完之后临时厨房会被删掉。你自己的 `kitchenette.db` 和正在跑的服务不会被碰到。

**关于快进钟**（`server.dev_clock`，上面那个脚本只在它自己起的服务上用）：它拨的是整台服务的钟。那个库里的所有角色会一起往前跳，大家的菜一起变坏、饱食度一起掉。正在用的厨房千万别开。

## 开发

```sh
pip install -e '.[dev]'
pytest
```

测试不会碰你的 `kitchenette.db`：每一条都用临时文件夹里的库。
