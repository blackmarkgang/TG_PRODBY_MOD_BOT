import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Check,
  Download,
  ExternalLink,
  Eye,
  FileText,
  Hash,
  Plus,
  Play,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldBan,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import "./styles.css";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready: () => void;
        expand: () => void;
      };
    };
  }
}

type Role = { code: string; title: string };

type ApplicationFile = {
  id: number;
  file_type: string;
  file_name: string | null;
  mime_type: string | null;
  file_size: number | null;
  url: string | null;
  caption: string | null;
};

type Application = {
  id: number;
  status: string;
  age: number | null;
  answers: Record<string, string>;
  files: ApplicationFile[];
  roles: Role[];
  created_at: string;
  admin_comment: string | null;
  reviewed_at: string | null;
  user: {
    telegram_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
    is_banned: boolean;
  };
};

type Participant = {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  created_at: string;
  is_banned: boolean;
  roles: Role[];
  latest_application_status: string | null;
};

type Topic = {
  id: number;
  chat_id: number;
  message_thread_id: number;
  title: string;
  is_protected: boolean;
  allowed_roles: Role[];
};

type Tab = "applications" | "participants" | "settings";
type PreviewKind = "audio" | "video" | "image" | "pdf" | null;

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const devAdminId = import.meta.env.VITE_DEV_ADMIN_ID ?? "";

const statusLabels: Record<string, string> = {
  pending: "На рассмотрении",
  approved: "Одобрена",
  rejected: "Отклонена",
  banned: "Заблокирована",
};

const participantStatusLabels: Record<string, string> = {
  pending: "Ожидает решения",
  approved: "Принят",
  rejected: "Отклонен",
  banned: "Заблокирован",
};

const answerLabels: Record<string, string> = {
  role_details: "О себе и пользе для сообщества",
  listener_artists: "Кого слушает",
  listener_follows: "За кем следит",
  listener_likes: "Что нравится в музыке",
  motivation: "Почему хочет попасть в Prod.by",
  expectations: "Ожидания от участия",
};

const fileTypeLabels: Record<string, string> = {
  audio: "Аудио",
  document: "Документ",
  video: "Видео",
  voice: "Голосовое сообщение",
  photo: "Изображение",
  url: "Ссылка",
};

function authHeaders(initData: string): Record<string, string> {
  if (initData) return { Authorization: `tma ${initData}` };
  return devAdminId ? { "X-Dev-Admin-ID": devAdminId } : {};
}

async function getApiError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return payload.detail ?? `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

function formatFileSize(size: number | null): string {
  if (size === null) return "";
  if (size < 1024 * 1024) return `${Math.ceil(size / 1024)} КБ`;
  return `${(size / 1024 / 1024).toFixed(1)} МБ`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function getPreviewKind(file: ApplicationFile): PreviewKind {
  const mimeType = file.mime_type ?? "";
  if (file.file_type === "audio" || file.file_type === "voice" || mimeType.startsWith("audio/")) {
    return "audio";
  }
  if (file.file_type === "video" || mimeType.startsWith("video/")) return "video";
  if (file.file_type === "photo" || mimeType.startsWith("image/")) return "image";
  if (mimeType === "application/pdf" || file.file_name?.toLowerCase().endsWith(".pdf")) return "pdf";
  return null;
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>("applications");
  const [applications, setApplications] = useState<Application[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);
  const [topicRoleDrafts, setTopicRoleDrafts] = useState<Record<number, string[]>>({});
  const [topicTitleDrafts, setTopicTitleDrafts] = useState<Record<number, string>>({});
  const [newTopicId, setNewTopicId] = useState("");
  const [newTopicTitle, setNewTopicTitle] = useState("");
  const [participantSearch, setParticipantSearch] = useState("");
  const [editingParticipantId, setEditingParticipantId] = useState<number | null>(null);
  const [participantRoleDrafts, setParticipantRoleDrafts] = useState<Record<number, string[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [comments, setComments] = useState<Record<number, string>>({});
  const [applicationRoles, setApplicationRoles] = useState<Record<number, string[]>>({});
  const [previewUrls, setPreviewUrls] = useState<Record<number, string>>({});
  const [loadingPreviews, setLoadingPreviews] = useState<Set<number>>(new Set());
  const previewUrlsRef = useRef<Record<number, string>>({});
  const initData = useMemo(() => window.Telegram?.WebApp?.initData ?? "", []);
  const filteredParticipants = useMemo(() => {
    const query = participantSearch.trim().toLocaleLowerCase("ru-RU").replace(/^@/, "");
    if (!query) return participants;
    return participants.filter((participant) => (
      [participant.first_name, participant.last_name, participant.username, String(participant.telegram_id)]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("ru-RU")
        .includes(query)
    ));
  }, [participantSearch, participants]);

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    window.Telegram?.WebApp?.expand();
    void loadAll();
    return () => {
      Object.values(previewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  async function loadAll() {
    setError(null);
    const headers = authHeaders(initData);
    const [applicationsResponse, participantsResponse, rolesResponse, topicsResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/applications`, { headers }),
      fetch(`${apiBaseUrl}/participants`, { headers }),
      fetch(`${apiBaseUrl}/participants/roles`, { headers }),
      fetch(`${apiBaseUrl}/settings/topics`, { headers }),
    ]);

    const failedResponse = [applicationsResponse, participantsResponse, rolesResponse, topicsResponse].find(
      (response) => !response.ok,
    );
    if (failedResponse) {
      setError(`Не удалось загрузить данные: ${await getApiError(failedResponse)}`);
      return;
    }

    const loadedApplications: Application[] = await applicationsResponse.json();
    const loadedParticipants: Participant[] = await participantsResponse.json();
    setApplications(loadedApplications);
    setParticipants(loadedParticipants);
    setRoles(await rolesResponse.json());
    setApplicationRoles(Object.fromEntries(
      loadedApplications.map((application) => [application.id, application.roles.map((role) => role.code)]),
    ));
    setParticipantRoleDrafts(Object.fromEntries(
      loadedParticipants.map((participant) => [participant.id, participant.roles.map((role) => role.code)]),
    ));
    const loadedTopics: Topic[] = await topicsResponse.json();
    setTopics(loadedTopics);
    setTopicRoleDrafts(Object.fromEntries(loadedTopics.map((topic) => [topic.id, topic.allowed_roles.map((role) => role.code)])));
    setTopicTitleDrafts(Object.fromEntries(loadedTopics.map((topic) => [topic.id, topic.title])));
    setSelectedTopicId((current) => current ?? loadedTopics[0]?.id ?? null);
  }

  async function review(id: number, action: "approve" | "reject") {
    setError(null);
    setFeedback(null);
    const selectedRoles = applicationRoles[id] ?? [];
    if (action === "approve" && selectedRoles.length === 0) {
      setError("Перед одобрением выберите хотя бы одну роль участника.");
      return;
    }

    const response = await fetch(`${apiBaseUrl}/applications/${id}/${action}`, {
      method: "POST",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({
        comment: comments[id]?.trim() || null,
        role_codes: action === "approve" ? selectedRoles : [],
      }),
    });
    if (!response.ok) {
      setError(`Не удалось изменить статус заявки: ${await getApiError(response)}`);
      return;
    }

    const result = await response.json();
    setFeedback(
      result.warning ??
        (result.invite_created
          ? "Решение сохранено. Пользователю отправлена персональная ссылка на вход."
          : "Решение сохранено. Пользователь уведомлен."),
    );
    await loadAll();
  }

  async function banApplication(id: number) {
    const application = applications.find((item) => item.id === id);
    const displayName = application?.user.username
      ? `@${application.user.username}`
      : application?.user.first_name ?? `заявку №${id}`;
    if (!window.confirm(`Заблокировать ${displayName}? Пользователь потеряет доступ к группе и новым заявкам.`)) {
      return;
    }

    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/applications/${id}/ban`, {
      method: "POST",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ comment: comments[id]?.trim() || null, role_codes: [] }),
    });
    if (!response.ok) {
      setError(`Не удалось заблокировать пользователя: ${await getApiError(response)}`);
      return;
    }
    const result = await response.json();
    setFeedback(result.warning ?? "Пользователь заблокирован.");
    await loadAll();
  }

  async function resendNotification(id: number) {
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/applications/${id}/notify`, {
      method: "POST",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось отправить уведомление: ${await getApiError(response)}`);
      return;
    }
    const result = await response.json();
    setFeedback(
      result.warning ??
        (result.invite_created
          ? "Уведомление и новая персональная ссылка отправлены."
          : "Уведомление отправлено повторно."),
    );
  }

  function toggleApplicationRole(applicationId: number, roleCode: string) {
    setApplicationRoles((current) => {
      const selected = new Set(current[applicationId] ?? []);
      if (selected.has(roleCode)) selected.delete(roleCode);
      else selected.add(roleCode);
      return { ...current, [applicationId]: Array.from(selected) };
    });
  }

  function toggleParticipantRole(participantId: number, roleCode: string) {
    setParticipantRoleDrafts((current) => {
      const selected = new Set(current[participantId] ?? []);
      if (selected.has(roleCode)) selected.delete(roleCode);
      else selected.add(roleCode);
      return { ...current, [participantId]: Array.from(selected) };
    });
  }

  async function updateParticipantRoles(participantId: number) {
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/participants/${participantId}/roles`, {
      method: "PUT",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ role_codes: participantRoleDrafts[participantId] ?? [] }),
    });
    if (!response.ok) {
      setError(`Не удалось обновить роли: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Роли участника обновлены.");
    setEditingParticipantId(null);
    await loadAll();
  }

  function toggleTopicRole(topicId: number, roleCode: string) {
    setTopicRoleDrafts((current) => {
      const selected = new Set(current[topicId] ?? []);
      if (selected.has(roleCode)) selected.delete(roleCode);
      else selected.add(roleCode);
      return { ...current, [topicId]: Array.from(selected) };
    });
  }

  async function saveTopicPermissions(topic: Topic) {
    setError(null);
    setFeedback(null);
    const headers = { ...authHeaders(initData), "Content-Type": "application/json" };
    const title = topicTitleDrafts[topic.id]?.trim();
    if (!title) {
      setError("Укажите название темы.");
      return;
    }

    if (title !== topic.title) {
      const titleResponse = await fetch(`${apiBaseUrl}/settings/topics/${topic.id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ title }),
      });
      if (!titleResponse.ok) {
        setError(`Не удалось переименовать тему: ${await getApiError(titleResponse)}`);
        return;
      }
    }

    const rolesResponse = await fetch(`${apiBaseUrl}/settings/topics/${topic.id}/roles`, {
      method: "PUT",
      headers,
      body: JSON.stringify({ role_codes: topicRoleDrafts[topic.id] ?? [] }),
    });
    if (!rolesResponse.ok) {
      setError(`Не удалось сохранить права: ${await getApiError(rolesResponse)}`);
      return;
    }
    setFeedback("Права темы сохранены.");
    await loadAll();
  }

  async function createTopic() {
    setError(null);
    setFeedback(null);
    const messageThreadId = Number(newTopicId);
    if (!Number.isInteger(messageThreadId) || messageThreadId <= 0 || !newTopicTitle.trim()) {
      setError("Укажите корректный ID и название темы.");
      return;
    }
    const response = await fetch(`${apiBaseUrl}/settings/topics`, {
      method: "POST",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ message_thread_id: messageThreadId, title: newTopicTitle.trim() }),
    });
    if (!response.ok) {
      setError(`Не удалось добавить тему: ${await getApiError(response)}`);
      return;
    }
    const topic: Topic = await response.json();
    setNewTopicId("");
    setNewTopicTitle("");
    setSelectedTopicId(topic.id);
    setFeedback("Тема добавлена. Теперь выберите разрешенные роли.");
    await loadAll();
  }

  async function fetchFile(applicationId: number, file: ApplicationFile): Promise<Blob | null> {
    const response = await fetch(
      `${apiBaseUrl}/applications/${applicationId}/files/${file.id}/download`,
      { headers: authHeaders(initData) },
    );
    if (!response.ok) {
      setError(`Не удалось открыть вложение: ${await getApiError(response)}`);
      return null;
    }
    return response.blob();
  }

  async function downloadFile(applicationId: number, file: ApplicationFile) {
    setError(null);
    const blob = await fetchFile(applicationId, file);
    if (!blob) return;
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = file.file_name ?? `attachment-${file.id}`;
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  }

  async function loadPreview(applicationId: number, file: ApplicationFile) {
    if (previewUrls[file.id] || loadingPreviews.has(file.id)) return;
    setError(null);
    setLoadingPreviews((current) => new Set(current).add(file.id));
    try {
      const blob = await fetchFile(applicationId, file);
      if (!blob) return;
      const objectUrl = URL.createObjectURL(blob);
      previewUrlsRef.current[file.id] = objectUrl;
      setPreviewUrls((current) => ({ ...current, [file.id]: objectUrl }));
    } finally {
      setLoadingPreviews((current) => {
        const next = new Set(current);
        next.delete(file.id);
        return next;
      });
    }
  }

  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId) ?? null;

  return (
    <main className="shell">
      <header className="app-header">
        <div className="brand-block">
          <h1>PROD<b className="brand-dot">.</b>BY</h1>
          <span>Панель управления</span>
        </div>
        <button className="icon-button" onClick={loadAll} title="Обновить данные" aria-label="Обновить данные">
          <RefreshCw size={19} />
        </button>
      </header>

      <nav className="tabs" aria-label="Разделы панели">
        <button className={activeTab === "applications" ? "active" : ""} onClick={() => setActiveTab("applications")}>
          <FileText size={18} /> Заявки
        </button>
        <button className={activeTab === "participants" ? "active" : ""} onClick={() => setActiveTab("participants")}>
          <Users size={18} /> Участники
        </button>
        <button className={activeTab === "settings" ? "active" : ""} onClick={() => setActiveTab("settings")}>
          <Settings size={18} /> Настройки
        </button>
      </nav>

      {error && <div className="message error">{error}</div>}
      {feedback && <div className="message success-message">{feedback}</div>}
      {!initData && <div className="message notice">Локальный режим разработки</div>}

      {activeTab === "applications" && (
        <section className="section-content">
          <div className="section-heading">
            <div><h2>Заявки</h2><p>Рассмотрение кандидатов и назначение ролей</p></div>
            <span className="count">{applications.length}</span>
          </div>
          <div className="applications-grid">
            {applications.length === 0 && <div className="empty">Заявок пока нет.</div>}
            {applications.map((item) => (
              <article className="application-card" key={item.id}>
                <div className="card-head">
                  <div><strong>Заявка №{item.id}</strong><span>{formatDate(item.created_at)}</span></div>
                  <span className={`status ${item.status}`}>{statusLabels[item.status] ?? item.status}</span>
                </div>
                <div className="meta">
                  <span>{item.user.first_name ?? "Без имени"}</span>
                  <span>{item.user.username ? `@${item.user.username}` : `ID ${item.user.telegram_id}`}</span>
                  <span>Возраст: {item.age ?? "не указан"}</span>
                  {item.roles.length > 0 && <span>Роли: {item.roles.map((role) => role.title).join(", ")}</span>}
                </div>
                <dl>
                  {Object.entries(item.answers).map(([key, value]) => (
                    <React.Fragment key={key}><dt>{answerLabels[key] ?? key}</dt><dd>{value}</dd></React.Fragment>
                  ))}
                </dl>

                {item.files.length > 0 && (
                  <div className="attachments">
                    <h3>Вложения</h3>
                    {item.files.map((file) => {
                      const previewKind = getPreviewKind(file);
                      const previewUrl = previewUrls[file.id];
                      return (
                        <div className="file-entry" key={file.id}>
                          <div className="file-row">
                            <div className="file-info">
                              <strong>{file.file_name ?? fileTypeLabels[file.file_type] ?? "Вложение"}</strong>
                              <span>{fileTypeLabels[file.file_type] ?? file.file_type}{file.file_size ? ` · ${formatFileSize(file.file_size)}` : ""}</span>
                              {file.caption && <span>{file.caption}</span>}
                            </div>
                            <div className="file-actions">
                              {file.url ? (
                                <a className="icon-button" href={file.url} target="_blank" rel="noreferrer" title="Открыть ссылку"><ExternalLink size={18} /></a>
                              ) : (
                                <>
                                  {previewKind && !previewUrl && (
                                    <button className="icon-button" onClick={() => loadPreview(item.id, file)} title={previewKind === "audio" ? "Слушать" : "Смотреть"}>
                                      {previewKind === "audio" ? <Play size={18} /> : <Eye size={18} />}
                                    </button>
                                  )}
                                  <button className="icon-button" onClick={() => downloadFile(item.id, file)} title="Скачать"><Download size={18} /></button>
                                </>
                              )}
                            </div>
                          </div>
                          {loadingPreviews.has(file.id) && <div className="loading-line">Загрузка предпросмотра...</div>}
                          {previewUrl && previewKind === "audio" && <audio className="media-preview" controls src={previewUrl} />}
                          {previewUrl && previewKind === "video" && <video className="media-preview" controls src={previewUrl} />}
                          {previewUrl && previewKind === "image" && <img className="image-preview" src={previewUrl} alt={file.file_name ?? "Вложение"} />}
                          {previewUrl && previewKind === "pdf" && <iframe className="pdf-preview" src={previewUrl} title={file.file_name ?? "PDF"} />}
                        </div>
                      );
                    })}
                  </div>
                )}

                {item.status === "pending" ? (
                  <div className="review-block">
                    <label>Роли после одобрения</label>
                    <div className="role-choice-grid application-role-options">
                      {roles.map((role) => {
                        const checked = (applicationRoles[item.id] ?? []).includes(role.code);
                        return (
                          <label className={checked ? "selected" : ""} key={role.code}>
                            <input type="checkbox" checked={checked} onChange={() => toggleApplicationRole(item.id, role.code)} />
                            <span className="check-box">{checked && <Check size={15} />}</span>
                            <span>{role.title}</span>
                          </label>
                        );
                      })}
                    </div>
                    <label htmlFor={`comment-${item.id}`}>Комментарий пользователю (необязательно)</label>
                    <textarea id={`comment-${item.id}`} value={comments[item.id] ?? ""} onChange={(event) => setComments((current) => ({ ...current, [item.id]: event.target.value }))} rows={3} />
                    <div className="actions">
                      <button className="approve" onClick={() => review(item.id, "approve")}>Одобрить</button>
                      <button className="reject" onClick={() => review(item.id, "reject")}>Отклонить</button>
                      <button className="ban-button" onClick={() => banApplication(item.id)}><ShieldBan size={17} /> Забанить</button>
                    </div>
                  </div>
                ) : (
                  <div className="review-result">
                    {item.admin_comment && <p><strong>Комментарий:</strong> {item.admin_comment}</p>}
                    <div className="actions">
                      {["approved", "rejected"].includes(item.status) && <button onClick={() => resendNotification(item.id)}>Отправить уведомление повторно</button>}
                      {!item.user.is_banned && <button className="ban-button" onClick={() => banApplication(item.id)}><ShieldBan size={17} /> Забанить</button>}
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {activeTab === "participants" && (
        <section className="section-content">
          <div className="section-heading">
            <div><h2>Участники</h2><p>Все пользователи, сохранившиеся в базе</p></div>
            <span className="count">{filteredParticipants.length}</span>
          </div>
          <label className="participant-search">
            <Search size={18} />
            <input
              type="search"
              placeholder="Поиск по имени или @username"
              value={participantSearch}
              onChange={(event) => setParticipantSearch(event.target.value)}
            />
          </label>
          <div className="participants-table">
            <div className="participant-row table-head"><span>Пользователь</span><span>Статус</span><span>Выданные роли</span><span>Управление</span></div>
            {filteredParticipants.map((participant) => (
              <React.Fragment key={participant.id}>
                <div className="participant-row">
                  <div className="participant-name">
                    <strong>{[participant.first_name, participant.last_name].filter(Boolean).join(" ") || "Без имени"}</strong>
                    <span>{participant.username ? `@${participant.username}` : `Telegram ID: ${participant.telegram_id}`}</span>
                  </div>
                  <span className={`participant-status ${participant.is_banned ? "banned" : participant.latest_application_status ?? "none"}`}>
                    {participant.is_banned ? "Заблокирован" : participant.latest_application_status ? participantStatusLabels[participant.latest_application_status] : "Без заявки"}
                  </span>
                  <div className="role-badges">
                    {participant.roles.map((role) => <span key={role.code}>{role.title}</span>)}
                    {participant.roles.length === 0 && <em>Нет ролей</em>}
                  </div>
                  <button
                    className={`manage-roles ${editingParticipantId === participant.id ? "active" : ""}`}
                    disabled={participant.is_banned}
                    title={participant.is_banned ? "Заблокированному пользователю нельзя назначать роли" : "Управление ролями"}
                    onClick={() => setEditingParticipantId((current) => current === participant.id ? null : participant.id)}
                  >
                    <SlidersHorizontal size={17} /> Роли
                  </button>
                </div>
                {editingParticipantId === participant.id && (
                  <div className="participant-role-editor">
                    <div className="role-choice-grid">
                      {roles.map((role) => {
                        const checked = (participantRoleDrafts[participant.id] ?? []).includes(role.code);
                        return (
                          <label className={checked ? "selected" : ""} key={role.code}>
                            <input type="checkbox" checked={checked} onChange={() => toggleParticipantRole(participant.id, role.code)} />
                            <span className="check-box">{checked && <Check size={15} />}</span>
                            <span>{role.title}</span>
                          </label>
                        );
                      })}
                    </div>
                    <button className="save-permissions" onClick={() => updateParticipantRoles(participant.id)}><Save size={17} /> Сохранить роли</button>
                  </div>
                )}
              </React.Fragment>
            ))}
            {filteredParticipants.length === 0 && <div className="empty">Ничего не найдено.</div>}
          </div>
        </section>
      )}

      {activeTab === "settings" && (
        <section className="section-content">
          <div className="section-heading">
            <div><h2>Права тем</h2><p>Роли, которым разрешено публиковать сообщения</p></div>
            <span className="count">{topics.length}</span>
          </div>

          <div className="topic-settings">
            <div className="topic-list" aria-label="Темы группы">
              {topics.map((topic) => (
                <button
                  className={`topic-item ${selectedTopicId === topic.id ? "active" : ""}`}
                  key={topic.id}
                  onClick={() => setSelectedTopicId(topic.id)}
                >
                  <Hash size={18} />
                  <span><strong>{topic.title}</strong><small>ID {topic.message_thread_id}</small></span>
                  <em>{topic.allowed_roles.length || "Все"}</em>
                </button>
              ))}
              {topics.length === 0 && <div className="empty compact">Темы появятся после новых сообщений в группе.</div>}
            </div>

            <div className="topic-editor">
              {selectedTopic ? (
                <>
                  <div className="editor-heading">
                    <div><span>Настройка темы</span><strong>{selectedTopic.title}</strong></div>
                    <Hash size={22} />
                  </div>
                  <label htmlFor={`topic-title-${selectedTopic.id}`}>Название в панели</label>
                  <input
                    id={`topic-title-${selectedTopic.id}`}
                    value={topicTitleDrafts[selectedTopic.id] ?? selectedTopic.title}
                    onChange={(event) => setTopicTitleDrafts((current) => ({ ...current, [selectedTopic.id]: event.target.value }))}
                  />
                  <div className="role-editor-heading">
                    <strong>Кто может писать</strong>
                    <span>Если ничего не выбрано, писать могут все</span>
                  </div>
                  <div className="role-options">
                    {roles.map((role) => {
                      const checked = (topicRoleDrafts[selectedTopic.id] ?? []).includes(role.code);
                      return (
                        <label className={checked ? "selected" : ""} key={role.code}>
                          <input type="checkbox" checked={checked} onChange={() => toggleTopicRole(selectedTopic.id, role.code)} />
                          <span className="check-box">{checked && <Check size={15} />}</span>
                          <span>{role.title}</span>
                        </label>
                      );
                    })}
                  </div>
                  <button className="save-permissions" onClick={() => saveTopicPermissions(selectedTopic)}>
                    <Save size={17} /> Сохранить права
                  </button>
                </>
              ) : (
                <div className="editor-empty"><Settings size={28} /><span>Выберите тему для настройки</span></div>
              )}
            </div>
          </div>

          <div className="manual-topic">
            <div><strong>Добавить старую тему</strong><span>Для тем, которые бот еще не обнаружил</span></div>
            <div className="manual-topic-form">
              <input inputMode="numeric" placeholder="ID темы" value={newTopicId} onChange={(event) => setNewTopicId(event.target.value)} />
              <input placeholder="Название темы" value={newTopicTitle} onChange={(event) => setNewTopicTitle(event.target.value)} />
              <button className="icon-button" onClick={createTopic} title="Добавить тему" aria-label="Добавить тему"><Plus size={19} /></button>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
