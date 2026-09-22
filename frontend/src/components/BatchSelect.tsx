import { useEffect, useState } from "react";
import { api } from "../api/client";

export type Batch = {
  id: number;
  route_id: number;
  bag_count: number;
  reject_count: number;
  created_at: string;
};

export function useBatches() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState<number | "">("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    api<Batch[]>("/batches")
      .then((rows) => {
        setBatches(rows);
        setBatchId((cur) => cur || rows[0]?.id || "");
      })
      .catch(() => {});
  }, [reloadKey]);

  return { batches, batchId, setBatchId, reload: () => setReloadKey((k) => k + 1) };
}

export default function BatchSelect({
  batches,
  value,
  onChange,
}: {
  batches: Batch[];
  value: number | "";
  onChange: (id: number) => void;
}) {
  if (!batches.length) return null;
  const isLatest = (b: Batch) => b.id === batches[0].id;
  return (
    <label className="batch-pick">
      批次
      <select value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {batches.map((b) => (
          <option key={b.id} value={b.id}>
            #{b.id}
            {isLatest(b) ? "（最新）" : ""} · {new Date(b.created_at).toLocaleString()} · 路线 {b.route_id}
          </option>
        ))}
      </select>
    </label>
  );
}
