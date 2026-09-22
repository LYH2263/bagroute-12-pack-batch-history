import { useEffect, useState } from "react";
import { api } from "../api/client";
import BatchSelect, { useBatches } from "../components/BatchSelect";
type Rj = { id: number; batch_id: number | null; route_id: number; stop_name: string; reason: string; created_at: string };
export default function RejectsPage() {
  const { batches, batchId, setBatchId } = useBatches();
  const [rows, setRows] = useState<Rj[]>([]);
  useEffect(() => {
    if (batchId === "") { setRows([]); return; }
    api<Rj[]>(`/rejects?batch_id=${batchId}`).then(setRows).catch(() => setRows([]));
  }, [batchId]);
  return (<>
    <h2>拒收</h2>
    <div className="toolbar">
      <BatchSelect batches={batches} value={batchId} onChange={setBatchId} />
      {batchId !== "" && <span className="mono">批次 #{batchId}</span>}
    </div>
    <table className="table"><thead><tr><th>批次</th><th>时间</th><th>路线</th><th>订户</th><th>原因</th></tr></thead>
    <tbody>{rows.map(r => <tr key={r.id}><td>#{r.batch_id ?? "-"}</td><td className="mono">{new Date(r.created_at).toLocaleString()}</td><td>{r.route_id}</td><td>{r.stop_name}</td><td>{r.reason}</td></tr>)}
      {batchId === "" && <tr><td colSpan={5}>暂无批次，请先执行装袋</td></tr>}
      {batchId !== "" && !rows.length && <tr><td colSpan={5}>该批次暂无拒收</td></tr>}
    </tbody></table>
  </>);
}
