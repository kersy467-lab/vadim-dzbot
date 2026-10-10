"""Execute next-game browser JS to verify selection races and mutation routing."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def run_node(script):
    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


def test_selected_item_race_keeps_newest_view_and_navigation_cancels_pending_read():
    run_node(r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
const source = fs.readFileSync('frontend/natbirzha/js/screens/next_game_market.js', 'utf8').replace(/^import .*;\r?\n/gm, '');
const prefix = 'const NatAPI = {}; const esc = (x) => x; const renderNextMarketItem = () => {}; const renderCommodityCatalog = () => {};';
const {loadSelectedMarketItem} = await import('data:text/javascript;base64,' + Buffer.from(prefix + source).toString('base64'));
let marker;
const container = {
  set innerHTML(html) { if (marker) marker.isConnected = false; marker = {isConnected:true}; },
  querySelector() {return marker;},
};
let resolveFirst, resolveSecond;
const first = new Promise(r => resolveFirst = r), second = new Promise(r => resolveSecond = r);
const visible = [];
const a = loadSelectedMarketItem(container, 'steel', () => first, data => visible.push(data), assert.fail);
const b = loadSelectedMarketItem(container, 'coal', () => second, data => visible.push(data), assert.fail);
resolveSecond('coal'); await b;
resolveFirst('steel'); await a;
assert.deepEqual(visible, ['coal']);
let resolveThird;
const third = loadSelectedMarketItem(container, 'energy', () => new Promise(r => resolveThird=r), data => visible.push(data), assert.fail);
container.innerHTML = 'Navigated to bank';
resolveThird('energy'); await third;
assert.deepEqual(visible, ['coal']);
""")


def test_item_forms_route_only_to_isolated_api_and_advance_lock_hides_cancel():
    run_node(r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
const source = fs.readFileSync('frontend/natbirzha/js/screens/next_game_market_item.js', 'utf8').replace(/^import .*;\r?\n/gm, '');
const prefix = 'const renderMarketChart = () => "chart"; const getItemInfo = () => ({icon:"steel"});';
const {renderNextMarketItem} = await import('data:text/javascript;base64,' + Buffer.from(prefix + source).toString('base64'));
globalThis.window = {NatIcons:{icon:()=>''}};
globalThis.FormData = class { constructor(form){this.values=form.values;} get(key){return this.values[key];} };
const elements = new Map();
for (const selector of ['.next-market','.market-back','[data-book-refresh]','[data-npc-form]','[data-limit-form]']) {
  elements.set(selector, {isConnected:true,dataset:{},handlers:{},addEventListener(name,fn){this.handlers[name]=fn;},querySelectorAll(){return [];}});
}
const cancel = {dataset:{cancelOrder:'12'},handlers:{},addEventListener(name,fn){this.handlers[name]=fn;}};
const container = {innerHTML:'',querySelector(selector){return elements.get(selector);},querySelectorAll(selector){return selector==='[data-cancel-order]'?[cancel]:[];}};
const calls=[]; let refreshes=0, reloads=0;
renderNextMarketItem(container, {
  item:{id:'energy',name:'Энергия<script>',unit:'МВт·ч',base_price:10},npc:{buy_price:12,sell_price:8,treasury_cash:100,treasury_quantity:100},
  asks:[],bids:[],history:[],inventory_quantity:10,cash:100,advance_reference_price:8,
  user_orders:[{id:11,side:'SELL',status:'OPEN',remaining_quantity:10,limit_price:8,advance_locked:true,advance_paid:80,outstanding_amount:80}],
}, {api:{tradeNextGameMarket:async(...args)=>calls.push(['npc',...args]),createNextGameLimitOrder:async(...args)=>calls.push(['order',...args]),cancelNextGameOrder:async(...args)=>calls.push(['cancel',...args])},
  onBack(){},showToast(){},refresh:async()=>refreshes++,reload:async()=>reloads++});
assert.ok(!container.innerHTML.includes('data-cancel-order="11"'));
assert.ok(container.innerHTML.includes('Энергия&lt;script&gt;'));
const flush = async()=>{await new Promise(r=>setImmediate(r));};
elements.get('[data-npc-form]').handlers.submit({preventDefault(){},currentTarget:{values:{quantity:'2.5'}},submitter:{value:'SELL'}});
await flush();
elements.get('[data-limit-form]').handlers.submit({preventDefault(){},currentTarget:{values:{quantity:'3',price:'7',side:'BUY'}},submitter:{}});
await flush(); cancel.handlers.click(); await flush();
assert.deepEqual(calls,[['npc','energy','SELL',2.5],['order','energy','BUY',3,7],['cancel',12]]);
assert.equal(refreshes,3); assert.equal(reloads,3);
""")
