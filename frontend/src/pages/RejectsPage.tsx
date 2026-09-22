import { useEffect, useState } from "react";
import { api } from "../api/client";
type Rj = { id: number; route_id: number; batch_id: number; stop_name: string; reason: string; created_at: string };
type Batch = { id: number; route_id: number; batch_no: number; created_at: string };
export default function RejectsPage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState<number | "">("");
  const [rows, setRows] = useState<Rj[]>([]);
  useEffect(() => {
    api<Batch[]>("/batches").then(bs => {
      setBatches(bs);
      if (bs[0]) setBatchId(bs[0].id); // newest first, default latest
    });
  }, []);
  useEffect(() => {
    if (batchId === "") return;
    api<Rj[]>(`/rejects?batch_id=${batchId}`).then(setRows);
  }, [batchId]);
  return (<>
    <h2>拒收</h2>
    <div className="toolbar">
      <label>批次</label>
      <select value={batchId} onChange={e => setBatchId(Number(e.target.value))} disabled={!batches.length}>
        {batches.map(b => <option key={b.id} value={b.id}>批次 {b.batch_no} · 路线 {b.route_id} · {new Date(b.created_at).toLocaleString()}</option>)}
      </select>
      {!batches.length && <span>尚无批次，请先执行装袋</span>}
    </div>
    <table className="table"><thead><tr><th>时间</th><th>路线</th><th>订户</th><th>原因</th></tr></thead>
    <tbody>{rows.map(r => <tr key={r.id}><td className="mono">{new Date(r.created_at).toLocaleString()}</td><td>{r.route_id}</td><td>{r.stop_name}</td><td>{r.reason}</td></tr>)}
      {batches.length && !rows.length && <tr><td colSpan={4}>该批次暂无拒收</td></tr>}
      {!batches.length && <tr><td colSpan={4}>暂无拒收</td></tr>}
    </tbody></table>
  </>);
}
