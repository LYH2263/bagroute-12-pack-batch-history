import { useEffect, useState } from "react";
import { api } from "../api/client";
import BatchSelect, { useBatches } from "../components/BatchSelect";
type Bag = { id: number; batch_id: number; route_id: number; bag_index: number; weight_kg: number; volume_l: number; items: { stop_name: string; weight_kg: number; volume_l: number }[] };
export default function BagsPage() {
  const { batches, batchId, setBatchId } = useBatches();
  const [rows, setRows] = useState<Bag[]>([]);
  useEffect(() => {
    if (batchId === "") { setRows([]); return; }
    api<Bag[]>(`/bags?batch_id=${batchId}`).then(setRows).catch(() => setRows([]));
  }, [batchId]);
  return (<>
    <h2>袋明细</h2>
    <div className="toolbar">
      <BatchSelect batches={batches} value={batchId} onChange={setBatchId} />
      {batchId !== "" && <span className="mono">批次 #{batchId}</span>}
    </div>
    <table className="table"><thead><tr><th>批次</th><th>路线</th><th>袋号</th><th>重量</th><th>体积</th><th>订户</th></tr></thead>
    <tbody>{rows.map(b => <tr key={b.id}><td>#{b.batch_id}</td><td>{b.route_id}</td><td>{b.bag_index}</td><td className="mono">{b.weight_kg}</td><td className="mono">{b.volume_l}</td>
      <td>{b.items.map(i => i.stop_name).join(" → ")}</td></tr>)}
      {batchId === "" && <tr><td colSpan={6}>尚无装袋结果，请先执行装袋</td></tr>}
      {batchId !== "" && !rows.length && <tr><td colSpan={6}>该批次没有袋</td></tr>}
    </tbody></table>
  </>);
}
