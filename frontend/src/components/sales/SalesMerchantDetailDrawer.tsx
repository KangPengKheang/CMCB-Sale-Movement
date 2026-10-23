import React from "react";
import {
  ArrowLeft,
  Phone,
  MessageSquare,
  MapPin,
  ExternalLink,
  Clock,
  User,
  CheckCircle2,
  Calendar,
  Building2,
  FileText,
} from "lucide-react";
import { useSales } from "../../context/SalesContext";

export const SalesMerchantDetailDrawer: React.FC = () => {
  const {
    selectedMerchantId,
    selectedMerchantDetail,
    closeMerchantDetail,
  } = useSales();

  if (!selectedMerchantId) return null;

  if (!selectedMerchantDetail) {
    return (
      <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
        <div className="flex h-64 w-full max-w-lg items-center justify-center rounded-2xl bg-white shadow-xl">
          <div className="text-center">
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-cmcb-700 border-t-transparent" />
            <p className="text-xs font-semibold text-slate-500">Loading merchant profile...</p>
          </div>
        </div>
      </div>
    );
  }

  const m = selectedMerchantDetail;
  const isConverted = m.stage === "CONVERTED" || m.stage === "EXISTING";
  const isPipeline = m.stage === "PIPELINE";

  return (
    <div className="fixed inset-0 z-[2000] flex justify-end bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="flex h-full w-full max-w-xl flex-col bg-white shadow-2xl overflow-hidden animate-in slide-in-from-right duration-300">
        {/* Top Sticky Header with Back Button */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-5 py-4">
          <button
            onClick={closeMerchantDetail}
            className="flex items-center gap-1.5 text-xs font-bold text-cmcb-700 hover:text-cmcb-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <span className="text-xs font-semibold text-slate-400">Store Profile</span>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-5 lg:p-6 space-y-6">
          {/* Title & Stage */}
          <div>
            <h1 className="text-xl lg:text-2xl font-extrabold tracking-tight text-slate-900">
              {m.name}
            </h1>
            <p className="text-xs lg:text-sm text-slate-500 mt-1">
              {m.address} · <span className="font-semibold text-slate-700">{m.category}</span>
            </p>

            <div className="mt-3 flex items-center gap-2">
              <span
                className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                  isConverted
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                    : isPipeline
                    ? "bg-pipeline-50 text-pipeline-700 border border-pipeline-200"
                    : "bg-slate-100 text-slate-700 border border-slate-200"
                }`}
              >
                {m.stage}
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-600">
                {m.status}
              </span>
            </div>
          </div>

          {/* Assigned Salesperson Card */}
          <div className="rounded-2xl border border-slate-200/80 bg-slate-50/50 p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-cmcb-700 text-xs font-bold text-white shadow-sm">
                {m.assigned_reps.slice(0, 2).toUpperCase() || "RM"}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-slate-900 truncate">
                  {m.assigned_reps || "Unassigned"} {m.is_assigned_to_me && "(you)"}
                </p>
                <p className="text-[11px] text-slate-500">
                  {m.is_assigned_to_me ? "Assigned salesperson" : "Visiting teammate"}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 border-t border-slate-200/60">
              <div>
                <span className="text-slate-400">Last visit:</span>
                <p className="font-semibold text-slate-700 mt-0.5">
                  {m.last_visit_date ? m.last_visit_date.slice(0, 10) : "None recorded"}
                </p>
              </div>
              <div>
                <span className="text-slate-400">Next follow-up:</span>
                <p className="font-semibold text-cmcb-700 mt-0.5">Today · 1:00 PM</p>
              </div>
            </div>

            {/* Next step highlight */}
            <div className="rounded-xl bg-cmcb-50/80 p-3 border border-cmcb-200/60">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-cmcb-800">
                Next Step · POS Demo
              </span>
              <p className="text-xs font-medium text-cmcb-950 mt-1 leading-snug">
                Conduct live POS demo and explain end-of-day KHQR settlement report.
              </p>
            </div>
          </div>

          {/* Contact Card */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 space-y-3 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Your contact
            </h3>

            <div>
              <p className="text-sm font-bold text-slate-900">{m.contact.name}</p>
              <p className="text-[11px] text-slate-500">{m.contact.role}</p>
              <p className="text-xs font-semibold text-slate-800 mt-1">{m.contact.phone}</p>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-2">
              <a
                href={m.contact.phone !== "N/A" ? `tel:${m.contact.phone}` : "#"}
                className={`flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2 text-xs font-bold shadow-sm transition-colors ${
                  m.contact.phone !== "N/A"
                    ? "bg-white text-cmcb-700 hover:bg-cmcb-50"
                    : "bg-slate-50 text-slate-400 pointer-events-none"
                }`}
              >
                <Phone className="h-3.5 w-3.5" />
                Call
              </a>

              <a
                href={m.contact.phone !== "N/A" ? `https://t.me/+${m.contact.phone}` : "#"}
                target="_blank"
                rel="noreferrer"
                className={`flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2 text-xs font-bold shadow-sm transition-colors ${
                  m.contact.phone !== "N/A"
                    ? "bg-white text-slate-700 hover:bg-slate-50"
                    : "bg-slate-50 text-slate-400 pointer-events-none"
                }`}
              >
                <MessageSquare className="h-3.5 w-3.5" />
                Message
              </a>
            </div>
          </div>

          {/* POS Onboarding Stepper */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 space-y-3 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                POS onboarding
              </h3>
              <span className="text-xs font-semibold text-slate-400">
                Step {m.onboarding.current_step} of {m.onboarding.total_steps}
              </span>
            </div>

            <p className="text-sm font-extrabold text-slate-900">
              {m.onboarding.step_title}
            </p>

            {/* Step progress bar */}
            <div className="grid grid-cols-4 gap-1.5">
              {m.onboarding.steps.map((st, i) => {
                const isStepPassed = i + 1 <= m.onboarding.current_step;
                return (
                  <div key={st} className="space-y-1">
                    <div
                      className={`h-1.5 rounded-full transition-all ${
                        isStepPassed ? "bg-cmcb-700" : "bg-slate-200"
                      }`}
                    />
                    <span className="text-[10px] font-semibold text-slate-500 block truncate">
                      {st}
                    </span>
                  </div>
                );
              })}
            </div>

            <p className="text-xs text-slate-500 pt-1 leading-snug">
              {m.onboarding.step_description}
            </p>
          </div>

          {/* Notes Section */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 space-y-2 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Notes
            </h3>
            <p className="text-xs text-slate-700 leading-relaxed font-medium bg-slate-50 p-3 rounded-xl border border-slate-100">
              "{m.latest_note.text}"
            </p>
            <p className="text-[11px] text-slate-400">
              {m.latest_note.author} · Updated {m.latest_note.date}
            </p>
          </div>

          {/* Chronological Visit Timeline */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Visit timeline
              </h3>
              <span className="text-xs font-semibold text-slate-400">
                {m.timeline.length} {m.timeline.length === 1 ? "visit" : "visits"}
              </span>
            </div>

            <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              {m.timeline.map((item) => (
                <div key={item.id} className="relative">
                  {/* Dot */}
                  <div className="absolute -left-[23px] top-1 h-3 w-3 rounded-full border-2 border-white bg-cmcb-700 shadow-sm" />

                  <div>
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-xs font-bold text-slate-900">
                        {item.date_label} · {item.time}
                      </p>
                      <span className="text-[10px] font-semibold text-slate-400">
                        {item.rm_name}
                      </span>
                    </div>

                    <div className="mt-1">
                      <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-700">
                        {item.status} ({item.stage})
                      </span>
                    </div>

                    {item.remark && (
                      <p className="text-xs text-slate-600 mt-1 leading-snug">
                        {item.remark}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Location & Directions */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 flex items-center justify-between shadow-sm">
            <div className="min-w-0">
              <span className="text-xs font-bold text-slate-900">Store GPS Coordinates</span>
              <p className="text-xs text-slate-500 truncate mt-0.5">
                {m.latitude.toFixed(6)}, {m.longitude.toFixed(6)}
              </p>
            </div>

            <a
              href={m.map_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl bg-cmcb-700 px-3.5 py-2 text-xs font-bold text-white shadow-sm hover:bg-cmcb-800 transition-colors shrink-0"
            >
              <MapPin className="h-3.5 w-3.5" />
              Get directions
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
