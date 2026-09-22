import { useEffect, useState } from "react";
import { api } from "../api/client";
type Bag = { id: number; route_id: number; batch_id: number; bag_index: number; weight_kg: number; volume_l: number; items: { stop_name: string; weight_kg: number; volume_l: number }[] };
type Batch = { id: number; route_id: number; batch_no: number; created_at: string };
export default function BagsPage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState<number | "">("");
  const [rows, setRows] = useState<Bag[]>([]);
  useEffect(() => {
    api<Batch[]>("/batches").then(bs => {
      setBatches(bs);
      if (bs[0]) setBatchId(bs[0].id); // newest first, default latest
    });
  }, []);
  useEffect(() => {
    if (batchId === "") return;
    api<Bag[]>(`/bags?batch_id=${batchId}`).then(setRows);
  }, [batchId]);
  return (<>
    <h2>袋明细</h2>
    <div className="toolbar">
      <label>批次</label>
      <select value={batchId} onChange={e => setBatchId(Number(e.target.value))} disabled={!batches.length}>
        {batches.map(b => <option key={b.id} value={b.id}>批次 {b.batch_no} · 路线 {b.route_id} · {new Date(b.created_at).toLocaleString()}</option>)}
      </select>
      {!batches.length && <span>尚无批次，请先执行装袋</span>}
    </div>
    <table className="table"><thead><tr><th>路线</th><th>袋号</th><th>重量</th><th>体积</th><th>订户</th></tr></thead>
    <tbody>{rows.map(b => <tr key={b.id}><td>{b.route_id}</td><td>{b.bag_index}</td><td className="mono">{b.weight_kg}</td><td className="mono">{b.volume_l}</td>
      <td>{b.items.map(i => i.stop_name).join(" → ")}</td></tr>)}
      {batches.length && !rows.length && <tr><td colSpan={5}>该批次暂无袋明细</td></tr>}
      {!batches.length && <tr><td colSpan={5}>尚无装袋结果，请先执行装袋</td></tr>}
    </tbody></table>
  </>);
}
