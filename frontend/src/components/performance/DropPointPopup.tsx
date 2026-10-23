import React, { useEffect, useRef, useState } from "react";
import { Popup, useMap } from "react-leaflet";
import type L from "leaflet";
import { Building2, Phone, Briefcase, Landmark, Wallet, Percent, FileText, CalendarDays, Clock3, MapPin, RefreshCw, Loader2, type LucideIcon } from "lucide-react";
import type { DropDetail, MovementPoint } from "../../types";
import { fetchDropDetail } from "../../services/api";
import { startAutoRefresh } from "../../services/autoRefresh";

export function reportedValue(value: string | null | undefined): string | null {
  const text = value?.trim();
  return !text || /^(n\/?a|none|null|[-?])$/i.test(text) ? null : text;
}

function Field({ label, value, icon: Icon, featured = false }: {
  label: string; value: string | null | undefined; icon: LucideIcon; featured?: boolean;
}) {
  const text = reportedValue(value);
  return <div className={`min-w-0 rounded-xl border px-2 py-1.5 ${featured ? "border-teal-100 bg-gradient-to-br from-teal-50 to-cyan-50" : "border-slate-100 bg-slate-50/80"}`}>
    <dt className="mb-0.5 flex items-center gap-1 text-[8px] font-semibold uppercase tracking-wider text-slate-500"><Icon className="h-2.5 w-2.5" />{label}</dt>
    <dd className={`break-words leading-4 [overflow-wrap:anywhere] ${text ? featured ? "text-[12px] font-bold text-teal-800" : "text-[11px] font-semibold text-slate-800" : "text-[9px] font-medium text-slate-400"}`}>{text ?? "Not reported"}</dd>
  </div>;
}

function statusTone(value: string | null) {
  const text = value?.trim().toLowerCase() ?? "";
  if (/\b(not interested|rejected|refused|closed|declined)\b/.test(text)) return "border-rose-200 bg-rose-50 text-rose-700";
  if (/\b(signed|converted|existing|approved|active|deployed)\b/.test(text)) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (/\b(follow[ -]?up|pending|pipeline|ap)\b/.test(text)) return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-sky-200 bg-sky-50 text-sky-700";
}

const clock = (value: string) => new Date(value).toLocaleTimeString("en-GB", {
  timeZone: "Asia/Phnom_Penh", hour: "2-digit", minute: "2-digit", second: "2-digit",
});
const duration = (seconds: number) => seconds < 60 ? `${seconds}s` : seconds < 3600
  ? `${(seconds / 60).toFixed(1)} min` : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;

export function DropPointPopup({ point, senderName, color, label, gpsGap, autoOpen }: {
  point: MovementPoint; senderName: string; color: string; label: string; gpsGap: number | null;
  autoOpen: boolean;
}) {
  const map = useMap();
  const popupRef = useRef<L.Popup>(null);
  const cardRef = useRef<HTMLElement>(null);
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<DropDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (autoOpen) popupRef.current?.setLatLng([point.latitude, point.longitude]).openOn(map);
  }, [autoOpen, map, point.latitude, point.longitude]);
  useEffect(() => {
    if (!open) return;
    let alive = true;
    const stop = startAutoRefresh(async () => {
      const result = await fetchDropDetail(point.id);
      if (!alive) return;
      if (result) { setDetail(result); setFailed(false); }
      else setFailed(true);
    });
    return () => { alive = false; stop(); };
  }, [open, point.id, retry]);
  useEffect(() => {
    if (!open) return;
    let frame = 0;
    const update = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => popupRef.current?.update());
    };
    const observer = new ResizeObserver(update);
    observer.observe(map.getContainer());
    if (cardRef.current) observer.observe(cardRef.current);
    update();
    return () => { observer.disconnect(); window.cancelAnimationFrame(frame); };
  }, [open, map]);
  const tel = reportedValue(detail?.tel);
  const dial = tel?.replace(/[\s().-]/g, "") ?? "";
  const callable = /^\+?[0-9]{6,16}$/.test(dial);
  const loading = !detail && !failed;
  const status = reportedValue(detail?.status);
  return <Popup ref={popupRef} className="drop-detail-popup" minWidth={200} maxWidth={290}
    autoPanPaddingTopLeft={[52, 24]} autoPanPaddingBottomRight={[16, 20]} keepInView eventHandlers={{
      add: () => setOpen(true),
      remove: () => setOpen(false),
    }}>
    <article ref={cardRef} aria-label="Drop details" aria-busy={loading} className="drop-details-card" data-testid="drop-details-card">
      <header className="relative overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-3 pb-2.5 pt-2.5 text-white">
        <div className="absolute inset-x-0 top-0 h-0.5" style={{ background: `linear-gradient(90deg, ${color}, #22d3ee)` }} />
        <div className="mb-1.5 flex items-center gap-2 pr-6 text-[9px] font-semibold text-slate-300">
          <span className="rounded-full border border-white/15 bg-white/10 px-1.5 py-0.5 text-[8px] text-white">Visit #{point.drop_number}</span>
          <span className="inline-flex items-center gap-1 tabular-nums"><Clock3 className="h-2.5 w-2.5" />{clock(detail?.submitted_at ?? point.submitted_at)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-white/15 bg-white/10"><Building2 className="h-4 w-4 text-cyan-200" /></span>
          <div className="min-w-0">
            <div className="text-[8px] font-semibold uppercase tracking-wider text-cyan-200">Name</div>
            <h4 className="break-words text-[14px] font-bold leading-[18px] [overflow-wrap:anywhere]">{detail?.merchant_name ?? point.merchant_name}</h4>
          </div>
        </div>
        <div className="mt-1.5 flex items-center gap-1 text-[9px] text-slate-300"><span className="h-1 w-1 shrink-0 rounded-full" style={{ backgroundColor: color }} /><span className="truncate" title={detail?.sender_name ?? senderName}>{detail?.sender_name ?? senderName}</span></div>
      </header>
      <div className="space-y-2 bg-white px-3 py-2">
        {failed && <div role="status" className="flex items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-[9px] text-amber-900">
          <span>{detail ? "Update failed. Retrying automatically." : "Could not load this drop. Retrying automatically."}</span>
          <button onClick={() => setRetry(value => value + 1)} aria-label="Retry drop details" className="shrink-0 rounded bg-white p-1 shadow-sm"><RefreshCw className="h-3 w-3" /></button>
        </div>}
        {loading ? <div role="status" className="space-y-2 py-1">
          <span className="flex items-center gap-1.5 text-[10px] text-slate-500"><Loader2 className="h-3 w-3 animate-spin motion-reduce:animate-none" />Loading visit details…</span>
          <div className="h-8 rounded-lg bg-slate-100" /><div className="grid grid-cols-2 gap-1.5"><div className="h-10 rounded-lg bg-slate-50" /><div className="h-10 rounded-lg bg-slate-50" /></div>
        </div> : detail && <>
          <dl className="divide-y divide-slate-100">
            <div className="grid grid-cols-[62px_minmax(0,1fr)] items-start gap-2 py-1">
              <dt className="flex items-center gap-1 text-[9px] leading-4 text-slate-500"><Phone className="h-2.5 w-2.5 text-teal-600" />Tel</dt>
              <dd className="break-words text-[11px] font-semibold leading-4 [overflow-wrap:anywhere]">{callable ? <a className="drop-contact-link" href={`tel:${dial}`} aria-label={`Call ${tel}`}>{tel}</a> : <span className={tel ? "text-slate-800" : "text-[9px] font-normal text-slate-400"}>{tel ?? "Not reported"}</span>}</dd>
            </div>
            <div className="grid grid-cols-[62px_minmax(0,1fr)] items-start gap-2 py-1">
              <dt className="flex items-center gap-1 text-[9px] leading-4 text-slate-500"><Briefcase className="h-2.5 w-2.5 text-indigo-500" />Business</dt>
              <dd className="break-words text-[10px] font-medium leading-4 text-slate-800 [overflow-wrap:anywhere]">{reportedValue(detail.business) ?? <span className="text-[9px] font-normal text-slate-400">Not reported</span>}</dd>
            </div>
            <div className="grid grid-cols-[62px_minmax(0,1fr)] items-start gap-2 py-1">
              <dt className="flex items-center gap-1 text-[9px] leading-4 text-slate-500"><Landmark className="h-2.5 w-2.5 text-sky-600" />Bank</dt>
              <dd className="break-words text-[10px] font-medium leading-4 text-slate-800 [overflow-wrap:anywhere]">{reportedValue(detail.bank) ?? <span className="text-[9px] font-normal text-slate-400">Not reported</span>}</dd>
            </div>
            <div className="grid grid-cols-[62px_minmax(0,1fr)] items-start gap-2 py-1">
              <dt className="text-[9px] leading-4 text-slate-500">Status</dt>
              <dd><span className={`inline-block max-w-full break-words rounded-md border px-1.5 py-0.5 text-[9px] font-semibold leading-3 [overflow-wrap:anywhere] ${statusTone(status)}`}>{status ?? "Not reported"}</span></dd>
            </div>
          </dl>
          <dl className="grid grid-cols-2 gap-1.5">
            <Field label="Amount" value={detail.amount} icon={Wallet} featured />
            <Field label="Interest" value={detail.interest} icon={Percent} featured />
            <Field label="Loan type" value={detail.loan_type} icon={FileText} />
            <Field label="Maturity" value={detail.maturity} icon={CalendarDays} />
          </dl>
          <div className="flex items-center gap-1.5 border-t border-slate-100 pt-1.5 text-[8px] leading-3 text-slate-400">
            <span className="shrink-0 font-medium text-slate-500">Channel</span><span className="truncate" title={detail.source_channel}>{reportedValue(detail.source_channel) ?? "Unspecified channel"}</span>
          </div>
        </>}
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 border-t border-slate-100 bg-slate-50 px-3 py-1.5 text-[8px] leading-3 text-slate-500">
        <span className="inline-flex items-center gap-0.5 text-teal-700"><MapPin className="h-2.5 w-2.5" />{label}</span>
        {gpsGap !== null && <span className="inline-flex items-center gap-0.5"><Clock3 className="h-2.5 w-2.5" />{duration(gpsGap)} from prior GPS</span>}
      </footer>
    </article>
  </Popup>;
}
