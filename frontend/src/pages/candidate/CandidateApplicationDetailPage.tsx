import { useRef, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import Button from "@/components/ui/Button";
import CompanyName from "@/components/ui/CompanyName";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import Eyebrow from "@/components/ui/Eyebrow";
import PageHeader from "@/components/ui/PageHeader";
import { useFetch } from "@/hooks/useFetch";
import { useResetOnTrigger } from "@/hooks/useResetOnTrigger";
import {
  fetchApplicationResumeBlob,
  getMyApplication,
  patchMyApplication,
  withdrawApplication,
  type CandidateApplicationDetail,
  type CandidateApplicationMyAnswers,
} from "@/services/candidate";
import { TEXTAREA_CLS } from "@/styles/forms";

export default function CandidateApplicationDetailPage() {
  const { t } = useTranslation('candidate');
  const { id } = useParams();
  const navigate = useNavigate();
  const appId = Number(id);
  const [data, setData] = useState<CandidateApplicationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  // Edit mode
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<CandidateApplicationMyAnswers | null>(null);
  const [stagedResume, setStagedResume] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Withdraw
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);

  const { data: fetchedDetail, loading, error: fetchError } = useFetch(() => {
    if (!Number.isFinite(appId) || appId <= 0) {
      return Promise.reject(new Error("invalid_application_id"));
    }
    return getMyApplication(appId);
  }, [appId]);
  useResetOnTrigger(fetchedDetail, () => setData(fetchedDetail));
  useResetOnTrigger(fetchError, () => {
    if (axios.isAxiosError(fetchError) && fetchError.response?.status === 404) {
      setError(t("candidate:applications.errors.notFound"));
    } else if (fetchError instanceof Error && fetchError.message === "invalid_application_id") {
      setError(t("candidate:applications.errors.notFound"));
    } else {
      setError(t("candidate:applications.errors.loadFailed"));
    }
  });

  async function downloadResume() {
    if (!data?.resume || downloading) return;
    setDownloading(true);
    try {
      const blob = await fetchApplicationResumeBlob(data.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = data.resume.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError(t("candidate:applications.errors.generic"));
    } finally {
      setDownloading(false);
    }
  }

  function startEditing() {
    if (!data) return;
    setEditForm({ ...data.my_answers });
    setStagedResume(null);
    setSaveError(null);
    setIsEditing(true);
  }

  function cancelEditing() {
    setIsEditing(false);
    setEditForm(null);
    setStagedResume(null);
    setSaveError(null);
  }

  async function handleSave() {
    if (!data || !editForm) return;
    const form = new FormData();
    const orig = data.my_answers;
    if (editForm.service_concept !== orig.service_concept)
      form.append("service_concept", editForm.service_concept ?? "");
    if (editForm.salary_expectations !== orig.salary_expectations)
      form.append("salary_expectations", editForm.salary_expectations ?? "");
    if (editForm.strength !== orig.strength)
      form.append("strength", editForm.strength ?? "");
    if (editForm.growth_area !== orig.growth_area)
      form.append("growth_area", editForm.growth_area ?? "");
    if (stagedResume) form.append("resume", stagedResume, stagedResume.name);

    if ([...form.entries()].length === 0) {
      cancelEditing();
      return;
    }

    setSaving(true);
    setSaveError(null);
    try {
      const updated = await patchMyApplication(data.id, form);
      setData(updated);
      setIsEditing(false);
      setEditForm(null);
      setStagedResume(null);
    } catch (err) {
      if (
        axios.isAxiosError(err) &&
        err.response?.status === 409 &&
        err.response.data?.detail === "application_not_editable"
      ) {
        setSaveError(t("candidate:applications.edit.notEditable"));
        window.location.reload();
      } else {
        setSaveError(t("candidate:applications.errors.saveFailed"));
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleWithdraw() {
    if (!data) return;
    setWithdrawing(true);
    try {
      await withdrawApplication(data.id);
      navigate("/candidate/applications", { state: { withdrawn: true } });
    } catch (err) {
      if (
        axios.isAxiosError(err) &&
        err.response?.status === 409 &&
        err.response.data?.detail === "application_not_editable"
      ) {
        setWithdrawOpen(false);
        setError(t("candidate:applications.errors.notEditable"));
        window.location.reload();
      } else {
        setWithdrawOpen(false);
        setError(t("candidate:applications.errors.generic"));
      }
    } finally {
      setWithdrawing(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-white/60">{t("candidate:applications.loading")}</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-danger">{error}</p>
        <Link
          to="/candidate/applications"
          className="mt-4 inline-block text-sm text-white/60 hover:text-white/90"
        >
          {t("candidate:applications.detail.back")}
        </Link>
      </div>
    );
  }

  const answers = isEditing && editForm ? editForm : data.my_answers;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <PageHeader
        eyebrow={t("candidate:applications.detail.eyebrow")}
        subtitle={data.job.title}
      />

      <div className="mt-4 flex items-center justify-between">
        <Link
          to="/candidate/applications"
          className="text-xs text-white/50 hover:text-white/80"
        >
          ← {t("candidate:applications.detail.back")}
        </Link>

        {data.editable && !isEditing && (
          <div className="flex gap-3">
            <Button variant="primary" size="sm" onClick={startEditing}>
              {t("candidate:applications.edit.button")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setWithdrawOpen(true)}>
              {t("candidate:applications.withdraw.button")}
            </Button>
          </div>
        )}
      </div>

      <section className="mt-6 rounded-xl border border-white/8 bg-card p-6">
        <Eyebrow>{t("candidate:applications.detail.jobSection")}</Eyebrow>
        <div className="mt-3 flex flex-wrap items-baseline gap-3">
          <h3 className="text-xl text-white/90">{data.job.title}</h3>
          <CompanyName name={data.company.name} />
          {data.job.closed && (
            <span className="rounded-sm border border-white/15 px-2 py-0.5 text-[10px] uppercase tracking-widest text-white/50">
              {t("candidate:applications.closedPill")}
            </span>
          )}
        </div>
        <p className="mt-4 whitespace-pre-wrap text-sm text-white/70">
          {data.job.description}
        </p>
      </section>

      <section className="mt-6 rounded-xl border border-white/8 bg-card p-6">
        <Eyebrow>{t("candidate:applications.detail.myAnswers")}</Eyebrow>

        {isEditing && editForm ? (
          <div className="mt-4 space-y-4">
            <EditField
              label={t("candidate:applications.detail.answers.serviceConcept")}
              value={editForm.service_concept ?? ""}
              onChange={(v) => setEditForm({ ...editForm, service_concept: v || null })}
            />
            <EditField
              label={t("candidate:applications.detail.answers.salaryExpectations")}
              value={editForm.salary_expectations ?? ""}
              onChange={(v) =>
                setEditForm({ ...editForm, salary_expectations: v || null })
              }
            />
            <EditField
              label={t("candidate:applications.detail.answers.strength")}
              value={editForm.strength ?? ""}
              onChange={(v) => setEditForm({ ...editForm, strength: v || null })}
            />
            <EditField
              label={t("candidate:applications.detail.answers.growthArea")}
              value={editForm.growth_area ?? ""}
              onChange={(v) => setEditForm({ ...editForm, growth_area: v || null })}
            />
          </div>
        ) : (
          <dl className="mt-4 space-y-4">
            <AnswerRow
              label={t("candidate:applications.detail.answers.serviceConcept")}
              value={answers.service_concept}
              emptyLabel={t("candidate:applications.detail.answersEmpty")}
            />
            <AnswerRow
              label={t("candidate:applications.detail.answers.salaryExpectations")}
              value={answers.salary_expectations}
              emptyLabel={t("candidate:applications.detail.answersEmpty")}
            />
            <AnswerRow
              label={t("candidate:applications.detail.answers.strength")}
              value={answers.strength}
              emptyLabel={t("candidate:applications.detail.answersEmpty")}
            />
            <AnswerRow
              label={t("candidate:applications.detail.answers.growthArea")}
              value={answers.growth_area}
              emptyLabel={t("candidate:applications.detail.answersEmpty")}
            />
          </dl>
        )}
      </section>

      <section className="mt-6 rounded-xl border border-white/8 bg-card p-6">
        <Eyebrow>{t("candidate:applications.detail.resume")}</Eyebrow>

        {isEditing ? (
          <div className="mt-3 space-y-2">
            {stagedResume ? (
              <p className="text-sm text-white/70">
                {t("candidate:applications.edit.resumeStaged", {
                  filename: stagedResume.name,
                })}
              </p>
            ) : data.resume ? (
              <p className="truncate text-sm text-white/60">{data.resume.filename}</p>
            ) : (
              <p className="text-sm text-white/40">
                {t("candidate:applications.detail.resumeNone")}
              </p>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx"
              className="hidden"
              onChange={(e) => setStagedResume(e.target.files?.[0] ?? null)}
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              {t("candidate:applications.edit.resumeReplace")}
            </Button>
          </div>
        ) : data.resume ? (
          <div className="mt-3 flex items-center justify-between gap-4">
            <p className="truncate text-sm text-white/80">{data.resume.filename}</p>
            <Button
              size="sm"
              onClick={downloadResume}
              disabled={downloading}
              className="shrink-0"
            >
              {downloading
                ? t("candidate:applications.loading")
                : t("candidate:applications.detail.resumeDownload")}
            </Button>
          </div>
        ) : (
          <p className="mt-3 text-sm text-white/55">
            {t("candidate:applications.detail.resumeNone")}
          </p>
        )}
      </section>

      {isEditing && (
        <div className="mt-4 flex flex-col gap-3">
          {saveError && <p className="text-sm text-danger">{saveError}</p>}
          <div className="flex gap-3">
            <Button variant="primary" onClick={handleSave} disabled={saving}>
              {saving
                ? t("candidate:applications.loading")
                : t("candidate:applications.edit.save")}
            </Button>
            <Button variant="ghost" onClick={cancelEditing} disabled={saving}>
              {t("candidate:applications.edit.cancel")}
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={withdrawOpen}
        onOpenChange={(o) => !withdrawing && setWithdrawOpen(o)}
        title={t("candidate:applications.withdraw.title")}
        message={t("candidate:applications.withdraw.message")}
        confirmLabel={t("candidate:applications.withdraw.confirm")}
        variant="primary"
        isPending={withdrawing}
        onConfirm={handleWithdraw}
      />
    </div>
  );
}

function AnswerRow({
  label,
  value,
  emptyLabel,
}: {
  label: string;
  value: string | null;
  emptyLabel: string;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-white/50">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap text-sm text-white/85">
        {value && value.trim() ? value : <span className="text-white/40">{emptyLabel}</span>}
      </dd>
    </div>
  );
}

function EditField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wide text-white/50">{label}</label>
      <textarea
        className={`${TEXTAREA_CLS} mt-1`}
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
