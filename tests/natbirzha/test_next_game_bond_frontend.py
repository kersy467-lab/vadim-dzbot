from pathlib import Path
import subprocess


def test_bond_catalog_then_selected_series_actions_use_isolated_methods():
    script = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
const source = fs.readFileSync('frontend/natbirzha/js/screens/next_game_bonds.js','utf8').replace(/^import .*;\r?\n/gm,'');
const prefix = 'const NatAPI = {}; const esc = (x) => String(x); const number = (x) => String(x); const icon = () => "";';
const {renderNextGameBonds} = await import('data:text/javascript;base64,' + Buffer.from(prefix+source).toString('base64'));
globalThis.FormData = class {constructor(form){this.values=form.values;}get(key){return this.values[key];}};
const elements = new Map();
const node = (dataset={}) => ({dataset,handlers:{},addEventListener(name,fn){this.handlers[name]=fn;}});
for(const selector of ['[data-bond-bank]','[data-bond-back]','[data-bond-primary]','[data-bond-list]','[data-bond-secondary]']) elements.set(selector,node());
const series=node({bondSeries:'1'}), offer=node({bondOffer:'9'}), cancel=node({bondCancel:'10'});
const container={innerHTML:'',querySelector(selector){return elements.get(selector);},querySelectorAll(selector){
  if(selector==='[data-bond-series]')return [series]; if(selector==='[data-bond-offer]')return [offer]; if(selector==='[data-bond-cancel]')return [cancel]; return [];
}};
const calls=[];let refreshed=0;
const data={cash:1000,company_id:1,series:[{id:1,name:'7 дней',issuer:'Резервный банк',face_price:100,daily_rate:.001,term_days:7}],
  holdings:[{id:2,series_id:1,units:5,free_units:3,matures_at:'2026-10-17',acquired_at:'2026-10-10',next_coupon_at:'2026-10-10T13:00Z',coupon_paid:0}],
  listings:[{id:9,series_id:1,seller_name:'Другой',units:3,unit_price:101,matures_at:'2026-10-17',mine:false},{id:10,series_id:1,seller_name:'Мой',units:2,unit_price:99,matures_at:'2026-10-17',mine:true}]};
const state={nextGameAPI:{getNextGameBonds:async()=>data,buyNextGameBonds:async(...args)=>calls.push(['primary',...args]),
  listNextGameBonds:async(...args)=>calls.push(['list',...args]),buyNextGameBondListing:async(...args)=>calls.push(['secondary',...args]),cancelNextGameBondListing:async(...args)=>calls.push(['cancel',...args])}};
await renderNextGameBonds(container,state,()=>{},async()=>refreshed++);
assert.ok(!container.innerHTML.includes('data-bond-primary'));
series.handlers.click();
assert.ok(container.innerHTML.includes('data-bond-primary'));
const submit=(selector,values)=>elements.get(selector).handlers.submit({preventDefault(){},currentTarget:{values}});
const flush=()=>new Promise(r=>setImmediate(r));
submit('[data-bond-primary]',{units:'4'});await flush();
submit('[data-bond-list]',{holding_id:'2',units:'2',unit_price:'105'});await flush();
offer.handlers.click();submit('[data-bond-secondary]',{units:'1'});await flush();
cancel.handlers.click();await flush();
assert.deepEqual(calls,[['primary',1,4],['list',2,2,105],['secondary',9,1],['cancel',10]]);
assert.equal(refreshed,4);
"""
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=root,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
