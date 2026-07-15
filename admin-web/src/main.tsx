import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
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
  music_role: string | null;
  answers: Record<string, string>;
  files: ApplicationFile[];
  created_at: string;
  admin_comment: string | null;
  reviewed_at: string | null;
  user: {
    telegram_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
  };
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const devAdminId = import.meta.env.VITE_DEV_ADMIN_ID ?? "";

const statusLabels: Record<string, string> = {
  pending: "На рассмотрении",
  approved: "Одобрена",
  rejected: "Отклонена",
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

function formatFileSize(size: number | null): string {
  if (size === null) return "";
  if (size < 1024 * 1024) return `${Math.ceil(size / 1024)} КБ`;
  return `${(size / 1024 / 1024).toFixed(1)} МБ`;
}

function App() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [comments, setComments] = useState<Record<number, string>>({});
  const initData = useMemo(() => window.Telegram?.WebApp?.initData ?? "", []);

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    window.Telegram?.WebApp?.expand();
  }, []);

  async function loadApplications() {
    setError(null);
    const response = await fetch(`${apiBaseUrl}/applications`, {
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось загрузить заявки: ${response.status}`);
      return;
    }
    setApplications(await response.json());
  }

  async function review(id: number, action: "approve" | "reject") {
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/applications/${id}/${action}`, {
      method: "POST",
      headers: {
        ...authHeaders(initData),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ comment: comments[id]?.trim() || null }),
    });
    if (!response.ok) {
      setError(`Не удалось изменить статус заявки: ${response.status}`);
      return;
    }
    const result = await response.json();
    setFeedback(
      result.warning ??
        (result.invite_created
          ? "Решение сохранено. Пользователю отправлена персональная ссылка на вход."
          : "Решение сохранено. Пользователь уведомлен."),
    );
    await loadApplications();
  }

  async function resendNotification(id: number) {
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/applications/${id}/notify`, {
      method: "POST",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось отправить уведомление: ${response.status}`);
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

  async function downloadFile(applicationId: number, file: ApplicationFile) {
    setError(null);
    const response = await fetch(
      `${apiBaseUrl}/applications/${applicationId}/files/${file.id}/download`,
      { headers: authHeaders(initData) },
    );
    if (!response.ok) {
      setError(`Не удалось скачать файл: ${response.status}`);
      return;
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = file.file_name ?? `attachment-${file.id}`;
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  }

  useEffect(() => {
    void loadApplications();
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Prod.by — администратор</h1>
          <p>Заявки на вступление</p>
        </div>
        <button onClick={loadApplications}>Обновить</button>
      </header>

      {error && <div className="error">{error}</div>}
      {feedback && <div className="success-message">{feedback}</div>}
      {!initData && (
        <div className="notice">
          Локальный режим разработки. В Mini App будет использоваться авторизация Telegram.
        </div>
      )}

      <section className="grid">
        {applications.length === 0 && <div className="empty">Заявок пока нет.</div>}
        {applications.map((item) => (
          <article className="card" key={item.id}>
            <div className="card-head">
              <strong>Заявка №{item.id}</strong>
              <span className={`status ${item.status}`}>{statusLabels[item.status] ?? item.status}</span>
            </div>
            <div className="meta">
              <span>{item.user.first_name ?? "Без имени"}</span>
              <span>{item.user.username ? `@${item.user.username}` : "Без username"}</span>
              <span>Возраст: {item.age ?? "не указан"}</span>
              <span>Роль: {item.music_role ?? "не указана"}</span>
            </div>
            <dl>
              {Object.entries(item.answers).map(([key, value]) => (
                <React.Fragment key={key}>
                  <dt>{answerLabels[key] ?? key}</dt>
                  <dd>{value}</dd>
                </React.Fragment>
              ))}
            </dl>
            {item.files.length > 0 && (
              <div className="attachments">
                <h2>Вложения</h2>
                {item.files.map((file) => (
                  <div className="file-row" key={file.id}>
                    <div className="file-info">
                      <strong>{file.file_name ?? fileTypeLabels[file.file_type] ?? "Вложение"}</strong>
                      <span>
                        {fileTypeLabels[file.file_type] ?? file.file_type}
                        {file.file_size ? ` · ${formatFileSize(file.file_size)}` : ""}
                      </span>
                      {file.caption && <span>{file.caption}</span>}
                    </div>
                    {file.url ? (
                      <a className="link-button" href={file.url} target="_blank" rel="noreferrer">
                        Открыть
                      </a>
                    ) : (
                      <button onClick={() => downloadFile(item.id, file)}>Скачать</button>
                    )}
                  </div>
                ))}
              </div>
            )}
            {item.status === "pending" && (
              <div className="review-block">
                <label htmlFor={`comment-${item.id}`}>Комментарий пользователю (необязательно)</label>
                <textarea
                  id={`comment-${item.id}`}
                  value={comments[item.id] ?? ""}
                  onChange={(event) =>
                    setComments((current) => ({ ...current, [item.id]: event.target.value }))
                  }
                  rows={3}
                />
                <div className="actions">
                  <button className="approve" onClick={() => review(item.id, "approve")}>
                    Одобрить
                  </button>
                  <button className="reject" onClick={() => review(item.id, "reject")}>
                    Отклонить
                  </button>
                </div>
              </div>
            )}
            {item.status !== "pending" && (
              <div className="review-result">
                {item.admin_comment && (
                  <p><strong>Комментарий администрации:</strong> {item.admin_comment}</p>
                )}
                <button onClick={() => resendNotification(item.id)}>Отправить уведомление повторно</button>
              </div>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
