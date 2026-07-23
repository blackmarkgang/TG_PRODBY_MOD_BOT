import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDown,
  ArrowUp,
  BadgeCheck,
  Bot as BotIcon,
  Camera,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  Eye,
  FileText,
  Hash,
  ListChecks,
  MessageCircle,
  MoreHorizontal,
  Pause,
  Plus,
  Play,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Send,
  Settings,
  ShieldBan,
  SlidersHorizontal,
  Trash2,
  UserCog,
  UserCheck,
  UserMinus,
  Users,
  Volume2,
  XCircle,
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

type Role = { id?: number; code: string; title: string };

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
  answer_labels: Record<string, string>;
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
  is_group_member: boolean;
  has_used_bot: boolean;
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

type Question = {
  id: number;
  code: string;
  text: string;
  help_text: string | null;
  answer_type: "text" | "number" | "single_choice" | "file";
  options: QuestionOption[];
  next_question_code: string | null;
  sort_order: number;
};

type QuestionOption = {
  id: string;
  label: string;
  next_question_code: string | null;
};

type AuditEntry = {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  payload: Record<string, unknown>;
  admin_telegram_id: number | null;
  actor: {
    type: "admin" | "user" | "bot";
    telegram_id: number | null;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
  };
  created_at: string;
};

type BotStatus = {
  telegram_api: boolean;
  bot_id: number | null;
  username: string | null;
  mode: string;
};

type BotProfile = {
  id: number;
  username: string | null;
  name: string;
  short_description: string;
  description: string;
  avatar_id: string | null;
};

type BotTextSetting = {
  key: string;
  category: string;
  title: string;
  description: string;
  text: string;
  default_text: string;
  variables: string[];
  is_custom: boolean;
  updated_at: string | null;
};

type BotSettingsResponse = {
  profile: BotProfile;
  messages: BotTextSetting[];
};

type SupportAdmin = {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
};

type SupportMessage = {
  id: number;
  sender_type: "user" | "admin";
  text: string;
  created_at: string;
  admin: SupportAdmin | null;
};

type SupportTicket = {
  id: number;
  status: "open" | "in_progress" | "closed";
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  user: {
    id: number;
    telegram_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
  };
  assigned_admin: SupportAdmin | null;
  messages: SupportMessage[];
};

type StaffRole = "owner" | "admin" | "moderator";

type StaffUser = {
  id: number;
  telegram_id: number;
  role: StaffRole;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
};

type Tab = "applications" | "participants" | "support" | "settings" | "bot" | "logs";
type SettingsSection = "topics" | "roles" | "questions" | "access";
type PreviewKind = "audio" | "video" | "image" | "pdf" | null;
type ApplicationFilter = "all" | "pending" | "listener" | "artist" | "beatmaker" | "creative" | "approved" | "rejected";
type ParticipantSource = "group" | "bot";

const applicationFilters: { id: ApplicationFilter; label: string }[] = [
  { id: "all", label: "Все" },
  { id: "pending", label: "На рассмотрении" },
  { id: "listener", label: "Слушатель" },
  { id: "artist", label: "Артист" },
  { id: "beatmaker", label: "Битмейкер" },
  { id: "creative", label: "Креативный продакшн" },
  { id: "approved", label: "Одобренные" },
  { id: "rejected", label: "Отклонённые" },
];

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const devAdminId = import.meta.env.VITE_DEV_ADMIN_ID ?? "";

const statusLabels: Record<string, string> = {
  pending: "На рассмотрении",
  approved: "Одобрена",
  rejected: "Отклонена",
  banned: "Заблокирована",
  annulled: "Аннулирована",
};

const participantStatusLabels: Record<string, string> = {
  pending: "Ожидает решения",
  approved: "Принят",
  rejected: "Отклонен",
  banned: "Заблокирован",
  annulled: "Аннулирована",
};

const fileTypeLabels: Record<string, string> = {
  audio: "Аудио",
  document: "Документ",
  video: "Видео",
  voice: "Голосовое сообщение",
  photo: "Изображение",
  url: "Ссылка",
};

const auditActionLabels: Record<string, string> = {
  approve: "Заявка одобрена",
  annul_application: "Заявка аннулирована",
  reject: "Заявка отклонена",
  ban_user: "Пользователь заблокирован",
  application_submitted: "Заявка отправлена",
  assign_roles: "Роли участника изменены",
  set_topic_roles: "Права темы изменены",
  create_topic: "Тема добавлена",
  update_topic: "Тема обновлена",
  rename_topic: "Тема переименована",
  create_role: "Роль создана",
  update_role: "Роль изменена",
  delete_role: "Роль удалена",
  create_question: "Вопрос добавлен",
  update_question: "Вопрос изменен",
  delete_question: "Вопрос удален",
  reorder_questions: "Порядок вопросов изменен",
  moderation_denied: "Сообщение удалено модерацией",
  resend_notification: "Уведомление отправлено повторно",
  grant_staff_access: "Выдан доступ к панели",
  restore_staff_access: "Восстановлен доступ к панели",
  update_staff_access: "Изменены права сотрудника",
  revoke_staff_access: "Отозван доступ к панели",
  update_bot_profile: "Профиль бота изменен",
  update_bot_avatar: "Аватар бота изменен",
  remove_bot_avatar: "Аватар бота удален",
  update_bot_text: "Текст бота изменен",
  reset_bot_text: "Текст бота сброшен",
  support_ticket_created: "Создан тикет поддержки",
  support_ticket_claimed: "Тикет взят в работу",
  support_user_replied: "Пользователь ответил в тикете",
  support_admin_replied: "Администратор ответил в тикете",
  support_ticket_released: "Тикет передан в общую очередь",
  support_ticket_closed: "Тикет поддержки закрыт",
};

const staffRoleLabels: Record<StaffRole, string> = {
  owner: "Владелец",
  admin: "Администратор",
  moderator: "Модератор",
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

function formatMediaTime(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "00:00";
  const totalSeconds = Math.floor(value);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function formatApplicationDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value)).replace(",", "");
}

function getApplicationDirectionTitle(application: Application): string {
  return application.answers.role_details
    || application.roles.map((role) => role.title).join(", ")
    || "Без направления";
}

function formatLogDate(value: string): string {
  const date = new Date(value);
  const datePart = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
  }).format(date);
  const timePart = new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
  return `${datePart} ${timePart}`;
}

function formatActor(entry: AuditEntry): string {
  if (entry.actor.type === "bot") return "Бот";
  const type = entry.actor.type === "admin" ? "Администратор" : "Пользователь";
  const name = [entry.actor.first_name, entry.actor.last_name].filter(Boolean).join(" ");
  const username = entry.actor.username ? `@${entry.actor.username}` : "";
  const id = entry.actor.telegram_id ? `ID ${entry.actor.telegram_id}` : "";
  return [type, name, username, id].filter(Boolean).join(" · ");
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

function newQuestionOption(): QuestionOption {
  return {
    id: crypto.randomUUID().replace(/-/g, "").slice(0, 10),
    label: "",
    next_question_code: null,
  };
}

function getApplicationDirection(application: Application): "listener" | "artist" | "beatmaker" | "creative" | null {
  const direction = (application.answers.role_details ?? "").toLocaleLowerCase("ru-RU");
  if (
    direction.includes("креатив")
    || direction.includes("дизайн")
    || direction.includes("монтаж")
    || direction.includes("видео")
  ) return "creative";
  if (direction.includes("слушател")) return "listener";
  if (direction.includes("артист")) return "artist";
  if (direction.includes("битмейкер")) return "beatmaker";
  return null;
}

function applicationMatchesFilter(application: Application, filter: ApplicationFilter): boolean {
  if (filter === "all") return true;
  if (filter === "pending") return application.status === "pending";
  if (filter === "approved" || filter === "rejected") return application.status === filter;
  return application.status === "pending" && getApplicationDirection(application) === filter;
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>("applications");
  const [applicationFilter, setApplicationFilter] = useState<ApplicationFilter>("all");
  const [reviewingApplicationId, setReviewingApplicationId] = useState<number | null>(null);
  const [previewFile, setPreviewFile] = useState<{ applicationId: number; file: ApplicationFile } | null>(null);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [audioCurrentTime, setAudioCurrentTime] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [audioVolume, setAudioVolume] = useState(0.8);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("topics");
  const [applications, setApplications] = useState<Application[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [supportTickets, setSupportTickets] = useState<SupportTicket[]>([]);
  const [expandedSupportTicketId, setExpandedSupportTicketId] = useState<number | null>(null);
  const [supportReplyDrafts, setSupportReplyDrafts] = useState<Record<number, string>>({});
  const [roles, setRoles] = useState<Role[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [botProfile, setBotProfile] = useState<BotProfile | null>(null);
  const [botProfileDraft, setBotProfileDraft] = useState<BotProfile | null>(null);
  const [botMessages, setBotMessages] = useState<BotTextSetting[]>([]);
  const [botMessageDrafts, setBotMessageDrafts] = useState<Record<string, string>>({});
  const [botAvatarUrl, setBotAvatarUrl] = useState<string | null>(null);
  const [currentAdmin, setCurrentAdmin] = useState<StaffUser | null>(null);
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [staffRoleDrafts, setStaffRoleDrafts] = useState<Record<number, "admin" | "moderator">>({});
  const [newStaffTelegramId, setNewStaffTelegramId] = useState("");
  const [newStaffRole, setNewStaffRole] = useState<"admin" | "moderator">("moderator");
  const [roleTitleDrafts, setRoleTitleDrafts] = useState<Record<number, string>>({});
  const [questionDrafts, setQuestionDrafts] = useState<Record<number, Question>>({});
  const [newRoleTitle, setNewRoleTitle] = useState("");
  const [newQuestionText, setNewQuestionText] = useState("");
  const [newQuestionHelp, setNewQuestionHelp] = useState("");
  const [newQuestionType, setNewQuestionType] = useState<Question["answer_type"]>("text");
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);
  const [topicRoleDrafts, setTopicRoleDrafts] = useState<Record<number, string[]>>({});
  const [topicTitleDrafts, setTopicTitleDrafts] = useState<Record<number, string>>({});
  const [newTopicId, setNewTopicId] = useState("");
  const [newTopicTitle, setNewTopicTitle] = useState("");
  const [participantSearch, setParticipantSearch] = useState("");
  const [participantSource, setParticipantSource] = useState<ParticipantSource>("group");
  const [editingParticipantId, setEditingParticipantId] = useState<number | null>(null);
  const [participantRoleDrafts, setParticipantRoleDrafts] = useState<Record<number, string[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [comments, setComments] = useState<Record<number, string>>({});
  const [previewUrls, setPreviewUrls] = useState<Record<number, string>>({});
  const [loadingPreviews, setLoadingPreviews] = useState<Set<number>>(new Set());
  const previewUrlsRef = useRef<Record<number, string>>({});
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const supportRequestIdRef = useRef(0);
  const botAvatarUrlRef = useRef<string | null>(null);
  const avatarInputRef = useRef<HTMLInputElement | null>(null);
  const initData = useMemo(() => window.Telegram?.WebApp?.initData ?? "", []);
  const filteredParticipants = useMemo(() => {
    const query = participantSearch.trim().toLocaleLowerCase("ru-RU").replace(/^@/, "");
    return participants.filter((participant) => {
      const matchesSource = participantSource === "group"
        ? participant.is_group_member
        : participant.has_used_bot;
      if (!matchesSource) return false;
      if (!query) return true;
      return (
      [participant.first_name, participant.last_name, participant.username, String(participant.telegram_id)]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("ru-RU")
        .includes(query)
      );
    });
  }, [participantSearch, participantSource, participants]);
  const participantSourceCounts = useMemo(() => ({
    group: participants.filter((participant) => participant.is_group_member).length,
    bot: participants.filter((participant) => participant.has_used_bot).length,
  }), [participants]);
  const applicationFilterCounts = useMemo(() => Object.fromEntries(
    applicationFilters.map((filter) => [
      filter.id,
      applications.filter((application) => applicationMatchesFilter(application, filter.id)).length,
    ]),
  ) as Record<ApplicationFilter, number>, [applications]);
  const filteredApplications = useMemo(
    () => applications.filter((application) => applicationMatchesFilter(application, applicationFilter)),
    [applicationFilter, applications],
  );
  const activePreviewKind = previewFile ? getPreviewKind(previewFile.file) : null;
  const activePreviewUrl = previewFile
    ? previewFile.file.url ?? previewUrls[previewFile.file.id]
    : null;

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    window.Telegram?.WebApp?.expand();
    void loadAll();
    return () => {
      Object.values(previewUrlsRef.current)
        .filter((url) => url.startsWith("blob:"))
        .forEach((url) => URL.revokeObjectURL(url));
      if (botAvatarUrlRef.current) URL.revokeObjectURL(botAvatarUrlRef.current);
    };
  }, []);

  useEffect(() => {
    if (activeTab !== "support" || !currentAdmin) return;
    const intervalId = window.setInterval(() => {
      void loadSupportTickets(true);
    }, 3000);
    return () => window.clearInterval(intervalId);
  }, [activeTab, currentAdmin, initData]);

  useEffect(() => {
    if (!previewFile) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeApplicationPreview();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [previewFile]);

  useEffect(() => {
    setAudioCurrentTime(0);
    setAudioDuration(0);
    setAudioPlaying(false);
  }, [previewFile?.file.id]);

  useEffect(() => {
    if (audioPlayerRef.current) audioPlayerRef.current.volume = audioVolume;
  }, [audioVolume]);

  useEffect(() => {
    const player = audioPlayerRef.current;
    if (activePreviewKind !== "audio" || !activePreviewUrl || !player) return;
    void player.play().catch(() => setAudioPlaying(false));
  }, [activePreviewKind, activePreviewUrl]);

  async function loadSupportTickets(silent = false) {
    const requestId = ++supportRequestIdRef.current;
    try {
      const response = await fetch(`${apiBaseUrl}/support`, {
        headers: authHeaders(initData),
        cache: "no-store",
      });
      if (!response.ok) {
        if (!silent) setError(`Не удалось обновить поддержку: ${await getApiError(response)}`);
        return;
      }
      const tickets: SupportTicket[] = await response.json();
      if (requestId === supportRequestIdRef.current) setSupportTickets(tickets);
    } catch {
      if (!silent) setError("Не удалось обновить поддержку.");
    }
  }

  async function loadAll() {
    setError(null);
    const headers = authHeaders(initData);
    try {
      const meResponse = await fetch(`${apiBaseUrl}/access/me`, { headers });
      if (!meResponse.ok) {
        setCurrentAdmin(null);
        setError(`Доступ к панели запрещен: ${await getApiError(meResponse)}`);
        return;
      }
      const loadedAdmin: StaffUser = await meResponse.json();
      const fullAccess = loadedAdmin.role === "owner" || loadedAdmin.role === "admin";
      setCurrentAdmin(loadedAdmin);

      const baseResponses = await Promise.all([
        fetch(`${apiBaseUrl}/applications`, { headers }),
        fetch(`${apiBaseUrl}/participants`, { headers }),
        fetch(`${apiBaseUrl}/settings/roles`, { headers }),
        fetch(`${apiBaseUrl}/support`, { headers }),
      ]);
      const failedBaseResponse = baseResponses.find((response) => !response.ok);
      if (failedBaseResponse) {
        setError(`Не удалось загрузить данные: ${await getApiError(failedBaseResponse)}`);
        return;
      }

      const loadedApplications: Application[] = await baseResponses[0].json();
      const loadedParticipants: Participant[] = await baseResponses[1].json();
      const loadedRoles: Role[] = await baseResponses[2].json();
      const loadedSupportTickets: SupportTicket[] = await baseResponses[3].json();
      setApplications(loadedApplications);
      setParticipants(loadedParticipants);
      setRoles(loadedRoles);
      setSupportTickets(loadedSupportTickets);
      setRoleTitleDrafts(Object.fromEntries(
        loadedRoles.filter((role) => role.id !== undefined).map((role) => [role.id!, role.title]),
      ));
      setParticipantRoleDrafts(Object.fromEntries(
        loadedParticipants.map((participant) => [participant.id, participant.roles.map((role) => role.code)]),
      ));

      if (!fullAccess) {
        setActiveTab((current) => current === "settings" || current === "bot" || current === "logs" ? "applications" : current);
        setTopics([]);
        setQuestions([]);
        setLogs([]);
        setBotStatus(null);
        setStaff([]);
        setBotProfile(null);
        setBotProfileDraft(null);
        setBotMessages([]);
        return;
      }

      const fullResponses = await Promise.all([
        fetch(`${apiBaseUrl}/settings/topics`, { headers }),
        fetch(`${apiBaseUrl}/settings/questions`, { headers }),
        fetch(`${apiBaseUrl}/logs`, { headers }),
        fetch(`${apiBaseUrl}/logs/status`, { headers }),
        fetch(`${apiBaseUrl}/access/admins`, { headers }),
        fetch(`${apiBaseUrl}/bot-settings`, { headers }),
      ]);
      const failedFullResponse = fullResponses.slice(0, 5).find((response) => !response.ok);
      if (failedFullResponse) {
        setError(`Не удалось загрузить данные: ${await getApiError(failedFullResponse)}`);
        return;
      }

      const loadedTopics: Topic[] = await fullResponses[0].json();
      const loadedQuestions: Question[] = await fullResponses[1].json();
      const loadedStaff: StaffUser[] = await fullResponses[4].json();
      setTopics(loadedTopics);
      setQuestions(loadedQuestions);
      setLogs(await fullResponses[2].json());
      setBotStatus(await fullResponses[3].json());
      setStaff(loadedStaff);
      if (fullResponses[5].ok) {
        const loadedBotSettings: BotSettingsResponse = await fullResponses[5].json();
        setBotProfile(loadedBotSettings.profile);
        setBotProfileDraft(loadedBotSettings.profile);
        setBotMessages(loadedBotSettings.messages);
        setBotMessageDrafts(Object.fromEntries(loadedBotSettings.messages.map((item) => [item.key, item.text])));
        await loadBotAvatar(loadedBotSettings.profile.avatar_id);
      } else {
        setBotProfile(null);
        setBotProfileDraft(null);
        setBotMessages([]);
      }
      setQuestionDrafts(Object.fromEntries(loadedQuestions.map((question) => [question.id, question])));
      setStaffRoleDrafts(Object.fromEntries(
        loadedStaff
          .filter((item) => item.role !== "owner")
          .map((item) => [item.id, item.role as "admin" | "moderator"]),
      ));
      setTopicRoleDrafts(Object.fromEntries(loadedTopics.map((topic) => [topic.id, topic.allowed_roles.map((role) => role.code)])));
      setTopicTitleDrafts(Object.fromEntries(loadedTopics.map((topic) => [topic.id, topic.title])));
      setSelectedTopicId((current) => current ?? loadedTopics[0]?.id ?? null);
    } catch {
      setError("Не удалось подключиться к API панели.");
    }
  }

  async function review(id: number, action: "approve" | "reject") {
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/applications/${id}/${action}`, {
      method: "POST",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({
        comment: comments[id]?.trim() || null,
        role_codes: [],
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
    setReviewingApplicationId(null);
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
    setReviewingApplicationId(null);
    await loadAll();
  }

  async function annulApplication(id: number) {
    if (!window.confirm("Аннулировать одобренную заявку? Выданные роли будут сняты, а пользователь сможет заполнить анкету заново.")) {
      return;
    }
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/applications/${id}/annul`, {
      method: "POST",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось аннулировать заявку: ${await getApiError(response)}`);
      return;
    }
    const result = await response.json();
    setFeedback(result.warning ?? "Заявка аннулирована. Пользователь может заполнить анкету повторно.");
    setReviewingApplicationId(null);
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

  async function updateSupportTicket(
    id: number,
    action: "claim" | "release" | "close",
  ) {
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/support/${id}/${action}`, {
      method: "POST",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось изменить тикет: ${await getApiError(response)}`);
      return;
    }
    const result = await response.json();
    const ticket: SupportTicket = result.ticket ?? result;
    setSupportTickets((current) => current.map((item) => item.id === id ? ticket : item));
    const messages = {
      claim: `Тикет №${id} взят в работу.`,
      release: `Тикет №${id} передан в общую очередь.`,
      close: `Тикет №${id} закрыт.`,
    };
    setFeedback(result.warning ?? messages[action]);
    await loadSupportTickets(true);
  }

  async function replyToSupportTicket(id: number) {
    const text = supportReplyDrafts[id]?.trim();
    if (!text) {
      setError("Введите ответ пользователю.");
      return;
    }
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/support/${id}/reply`, {
      method: "POST",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) {
      setError(`Не удалось отправить ответ: ${await getApiError(response)}`);
      return;
    }
    const result = await response.json();
    setSupportTickets((current) => current.map((item) => item.id === id ? result.ticket : item));
    setSupportReplyDrafts((current) => ({ ...current, [id]: "" }));
    setFeedback(result.warning ?? "Ответ отправлен пользователю.");
    await loadSupportTickets(true);
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

  async function createRole() {
    const title = newRoleTitle.trim();
    if (!title) {
      setError("Укажите название роли.");
      return;
    }
    const response = await fetch(`${apiBaseUrl}/settings/roles`, {
      method: "POST",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (!response.ok) {
      setError(`Не удалось создать роль: ${await getApiError(response)}`);
      return;
    }
    setNewRoleTitle("");
    setFeedback("Роль создана.");
    await loadAll();
  }

  async function saveRole(role: Role) {
    if (role.id === undefined) return;
    const title = roleTitleDrafts[role.id]?.trim();
    if (!title) {
      setError("Название роли не может быть пустым.");
      return;
    }
    const response = await fetch(`${apiBaseUrl}/settings/roles/${role.id}`, {
      method: "PATCH",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (!response.ok) {
      setError(`Не удалось сохранить роль: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Роль обновлена.");
    await loadAll();
  }

  async function deleteRole(role: Role) {
    if (role.id === undefined || !window.confirm(`Удалить роль «${role.title}»? Она будет снята со всех участников и тем.`)) return;
    const response = await fetch(`${apiBaseUrl}/settings/roles/${role.id}`, {
      method: "DELETE",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось удалить роль: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Роль удалена.");
    await loadAll();
  }

  async function createQuestion() {
    const text = newQuestionText.trim();
    if (!text) {
      setError("Введите текст вопроса.");
      return;
    }
    const response = await fetch(`${apiBaseUrl}/settings/questions`, {
      method: "POST",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        help_text: newQuestionHelp.trim() || null,
        answer_type: newQuestionType,
        options: [],
        next_question_code: null,
      }),
    });
    if (!response.ok) {
      setError(`Не удалось добавить вопрос: ${await getApiError(response)}`);
      return;
    }
    setNewQuestionText("");
    setNewQuestionHelp("");
    setNewQuestionType("text");
    setFeedback("Вопрос добавлен в конец анкеты.");
    await loadAll();
  }

  async function saveQuestion(questionId: number) {
    const question = questionDrafts[questionId];
    if (!question?.text.trim()) {
      setError("Текст вопроса не может быть пустым.");
      return;
    }
    if (question.answer_type === "single_choice") {
      const labels = question.options.map((option) => option.label.trim()).filter(Boolean);
      if (labels.length < 2) {
        setError("Добавьте минимум два заполненных варианта ответа.");
        return;
      }
      if (new Set(labels.map((label) => label.toLocaleLowerCase("ru"))).size !== labels.length) {
        setError("Варианты ответа не должны повторяться.");
        return;
      }
    }
    const response = await fetch(`${apiBaseUrl}/settings/questions/${questionId}`, {
      method: "PATCH",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({
        text: question.text.trim(),
        help_text: question.help_text?.trim() || null,
        answer_type: question.answer_type,
        options: question.answer_type === "single_choice"
          ? question.options.map((option) => ({ ...option, label: option.label.trim() }))
          : [],
        next_question_code: question.next_question_code,
      }),
    });
    if (!response.ok) {
      setError(`Не удалось сохранить вопрос: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Вопрос обновлен.");
    await loadAll();
  }

  function changeQuestionType(question: Question, answerType: Question["answer_type"]) {
    const options = answerType === "single_choice"
      ? (question.options.length > 0 ? question.options : [newQuestionOption(), newQuestionOption()])
      : [];
    setQuestionDrafts((current) => ({
      ...current,
      [question.id]: { ...question, answer_type: answerType, options },
    }));
  }

  function addQuestionOption(question: Question) {
    setQuestionDrafts((current) => ({
      ...current,
      [question.id]: { ...question, options: [...question.options, newQuestionOption()] },
    }));
  }

  function updateQuestionOption(question: Question, optionId: string, patch: Partial<QuestionOption>) {
    setQuestionDrafts((current) => ({
      ...current,
      [question.id]: {
        ...question,
        options: question.options.map((option) => option.id === optionId ? { ...option, ...patch } : option),
      },
    }));
  }

  function removeQuestionOption(question: Question, optionId: string) {
    setQuestionDrafts((current) => ({
      ...current,
      [question.id]: { ...question, options: question.options.filter((option) => option.id !== optionId) },
    }));
  }

  async function deleteQuestion(question: Question) {
    if (!window.confirm(`Удалить вопрос «${question.text}»?`)) return;
    const response = await fetch(`${apiBaseUrl}/settings/questions/${question.id}`, {
      method: "DELETE",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось удалить вопрос: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Вопрос удален.");
    await loadAll();
  }

  async function moveQuestion(questionId: number, direction: -1 | 1) {
    const index = questions.findIndex((question) => question.id === questionId);
    const targetIndex = index + direction;
    if (index < 0 || targetIndex < 0 || targetIndex >= questions.length) return;
    const reordered = [...questions];
    [reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
    setQuestions(reordered);
    const response = await fetch(`${apiBaseUrl}/settings/questions/order`, {
      method: "PUT",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ question_ids: reordered.map((question) => question.id) }),
    });
    if (!response.ok) {
      setError(`Не удалось изменить порядок: ${await getApiError(response)}`);
      await loadAll();
      return;
    }
    setFeedback("Порядок вопросов обновлен.");
    await loadAll();
  }

  async function addStaffMember() {
    const telegramId = Number(newStaffTelegramId);
    if (!Number.isSafeInteger(telegramId) || telegramId <= 0) {
      setError("Укажите корректный Telegram ID.");
      return;
    }
    setError(null);
    const response = await fetch(`${apiBaseUrl}/access/admins`, {
      method: "POST",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ telegram_id: telegramId, role: newStaffRole }),
    });
    if (!response.ok) {
      setError(`Не удалось выдать доступ: ${await getApiError(response)}`);
      return;
    }
    setNewStaffTelegramId("");
    setNewStaffRole("moderator");
    setFeedback("Доступ к панели выдан.");
    await loadAll();
  }

  async function saveStaffRole(staffMember: StaffUser) {
    const role = staffRoleDrafts[staffMember.id];
    if (!role) return;
    setError(null);
    const response = await fetch(`${apiBaseUrl}/access/admins/${staffMember.id}`, {
      method: "PATCH",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    if (!response.ok) {
      setError(`Не удалось изменить доступ: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Уровень доступа обновлен.");
    await loadAll();
  }

  async function revokeStaffAccess(staffMember: StaffUser) {
    const identity = staffMember.username ? `@${staffMember.username}` : `ID ${staffMember.telegram_id}`;
    if (!window.confirm(`Отозвать доступ к панели у ${identity}?`)) return;
    setError(null);
    const response = await fetch(`${apiBaseUrl}/access/admins/${staffMember.id}`, {
      method: "DELETE",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось отозвать доступ: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Доступ к панели отозван.");
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
    if (loadingPreviews.has(file.id)) return;
    setError(null);
    setPreviewUrls((current) => {
      const next = { ...current };
      delete next[file.id];
      return next;
    });
    setLoadingPreviews((current) => new Set(current).add(file.id));
    try {
      const response = await fetch(
        `${apiBaseUrl}/applications/${applicationId}/files/${file.id}/preview-token`,
        {
          method: "POST",
          headers: authHeaders(initData),
        },
      );
      if (!response.ok) {
        setError(`Не удалось открыть вложение: ${await getApiError(response)}`);
        return;
      }
      const payload: { token: string } = await response.json();
      const previewUrl = `${apiBaseUrl}/applications/${applicationId}/files/${file.id}/preview?token=${encodeURIComponent(payload.token)}`;
      previewUrlsRef.current[file.id] = previewUrl;
      setPreviewUrls((current) => ({ ...current, [file.id]: previewUrl }));
    } finally {
      setLoadingPreviews((current) => {
        const next = new Set(current);
        next.delete(file.id);
        return next;
      });
    }
  }

  function openApplicationFile(applicationId: number, file: ApplicationFile) {
    const previewKind = getPreviewKind(file);
    if (!previewKind) {
      if (file.url) {
        window.open(file.url, "_blank", "noopener,noreferrer");
      } else {
        void downloadFile(applicationId, file);
      }
      return;
    }

    setPreviewFile({ applicationId, file });
    if (!file.url) void loadPreview(applicationId, file);
  }

  function closeApplicationPreview() {
    audioPlayerRef.current?.pause();
    setPreviewFile(null);
    setAudioPlaying(false);
  }

  function toggleAudioPlayback() {
    const player = audioPlayerRef.current;
    if (!player || !activePreviewUrl) return;
    if (player.paused) {
      void player.play().catch(() => setAudioPlaying(false));
    } else {
      player.pause();
    }
  }

  function seekAudio(value: number) {
    const player = audioPlayerRef.current;
    if (!player) return;
    player.currentTime = value;
    setAudioCurrentTime(value);
  }

  function changeAudioVolume(value: number) {
    setAudioVolume(value);
    if (audioPlayerRef.current) audioPlayerRef.current.volume = value;
  }

  async function loadBotAvatar(avatarId: string | null) {
    if (botAvatarUrlRef.current) {
      URL.revokeObjectURL(botAvatarUrlRef.current);
      botAvatarUrlRef.current = null;
    }
    setBotAvatarUrl(null);
    if (!avatarId) return;

    const response = await fetch(`${apiBaseUrl}/bot-settings/avatar?v=${encodeURIComponent(avatarId)}`, {
      headers: authHeaders(initData),
    });
    if (!response.ok) return;
    const objectUrl = URL.createObjectURL(await response.blob());
    botAvatarUrlRef.current = objectUrl;
    setBotAvatarUrl(objectUrl);
  }

  async function saveBotProfile() {
    if (!botProfileDraft) return;
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/bot-settings/profile`, {
      method: "PUT",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({
        name: botProfileDraft.name.trim(),
        short_description: botProfileDraft.short_description.trim(),
        description: botProfileDraft.description.trim(),
      }),
    });
    if (!response.ok) {
      setError(`Не удалось обновить профиль: ${await getApiError(response)}`);
      return;
    }
    const profile: BotProfile = await response.json();
    setBotProfile(profile);
    setBotProfileDraft(profile);
    setFeedback("Профиль бота обновлен в Telegram.");
  }

  async function uploadBotAvatar(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError(null);
    setFeedback(null);
    const formData = new FormData();
    formData.append("avatar", file);
    const response = await fetch(`${apiBaseUrl}/bot-settings/avatar`, {
      method: "PUT",
      headers: authHeaders(initData),
      body: formData,
    });
    if (!response.ok) {
      setError(`Не удалось обновить аватар: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Аватар бота обновлен в Telegram.");
    await loadAll();
  }

  async function removeBotAvatar() {
    if (!botProfile?.avatar_id || !window.confirm("Удалить текущий аватар бота?")) return;
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/bot-settings/avatar`, {
      method: "DELETE",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось удалить аватар: ${await getApiError(response)}`);
      return;
    }
    setFeedback("Аватар бота удален.");
    await loadAll();
  }

  async function saveBotText(key: string) {
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/bot-settings/messages/${key}`, {
      method: "PUT",
      headers: { ...authHeaders(initData), "Content-Type": "application/json" },
      body: JSON.stringify({ text: botMessageDrafts[key] ?? "" }),
    });
    if (!response.ok) {
      setError(`Не удалось сохранить текст: ${await getApiError(response)}`);
      return;
    }
    const updated: BotTextSetting = await response.json();
    setBotMessages((current) => current.map((item) => item.key === key ? updated : item));
    setBotMessageDrafts((current) => ({ ...current, [key]: updated.text }));
    setFeedback(`Текст «${updated.title}» сохранен.`);
  }

  async function resetBotText(item: BotTextSetting) {
    if (!item.is_custom || !window.confirm(`Вернуть исходный текст «${item.title}»?`)) return;
    setError(null);
    setFeedback(null);
    const response = await fetch(`${apiBaseUrl}/bot-settings/messages/${item.key}`, {
      method: "DELETE",
      headers: authHeaders(initData),
    });
    if (!response.ok) {
      setError(`Не удалось сбросить текст: ${await getApiError(response)}`);
      return;
    }
    const updated: BotTextSetting = await response.json();
    setBotMessages((current) => current.map((currentItem) => currentItem.key === item.key ? updated : currentItem));
    setBotMessageDrafts((current) => ({ ...current, [item.key]: updated.text }));
    setFeedback(`Текст «${item.title}» восстановлен.`);
  }

  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId) ?? null;
  const hasFullAccess = currentAdmin?.role === "owner" || currentAdmin?.role === "admin";
  const botMessageCategories = Array.from(new Set(botMessages.map((item) => item.category)));
  const previewApplication = previewFile
    ? applications.find((application) => application.id === previewFile.applicationId) ?? null
    : null;
  const previewUserName = previewApplication
    ? [previewApplication.user.first_name, previewApplication.user.last_name].filter(Boolean).join(" ") || "Без имени"
    : "";
  const safeAudioDuration = Number.isFinite(audioDuration) ? audioDuration : 0;

  return (
    <main className={`shell ${activePreviewKind === "audio" ? "with-audio-player" : ""}`}>
      <header className="app-header">
        <div className="brand-block">
          <h1>PROD<b className="brand-dot">.</b>BY</h1>
          <span>{currentAdmin ? staffRoleLabels[currentAdmin.role] : "Панель управления"}</span>
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
        <button className={activeTab === "support" ? "active" : ""} onClick={() => setActiveTab("support")}>
          <MessageCircle size={18} /> Поддержка
          {supportTickets.some((ticket) => ticket.status !== "closed") && (
            <span className="tab-indicator">
              {supportTickets.filter((ticket) => ticket.status !== "closed").length}
            </span>
          )}
        </button>
        {hasFullAccess && <button className={activeTab === "settings" ? "active" : ""} onClick={() => setActiveTab("settings")}>
          <Settings size={18} /> Настройки
        </button>}
        {hasFullAccess && <button className={activeTab === "bot" ? "active" : ""} onClick={() => setActiveTab("bot")}>
          <BotIcon size={18} /> Настройка бота
        </button>}
        {hasFullAccess && <button className={activeTab === "logs" ? "active" : ""} onClick={() => setActiveTab("logs")}>
          <Activity size={18} /> Логи
        </button>}
      </nav>

      {error && <div className="message error">{error}</div>}
      {feedback && <div className="message success-message">{feedback}</div>}
      {!initData && <div className="message notice">Локальный режим разработки</div>}

      {activeTab === "applications" && (
        <section className="section-content">
          <div className="section-heading">
            <div><h2>Заявки</h2><p>Рассмотрение кандидатов</p></div>
            <span className="count">{filteredApplications.length}</span>
          </div>
          <div className="application-filter-tabs" role="tablist" aria-label="Фильтр заявок">
            {applicationFilters.map((filter) => (
              <button
                className={applicationFilter === filter.id ? "active" : ""}
                key={filter.id}
                onClick={() => setApplicationFilter(filter.id)}
                role="tab"
                aria-selected={applicationFilter === filter.id}
              >
                <span>{filter.label}</span>
                <em>{applicationFilterCounts[filter.id]}</em>
              </button>
            ))}
          </div>
          <div className="application-queue">
            <div className="compact-application-head">
              <span>Заявка</span><span>Пользователь</span><span>Направление</span><span>Примеры работ</span><span>Действия</span>
            </div>
            {filteredApplications.length === 0 && <div className="empty">В этой вкладке заявок нет.</div>}
            {filteredApplications.map((item) => {
              const reviewing = reviewingApplicationId === item.id;
              const displayName = [item.user.first_name, item.user.last_name].filter(Boolean).join(" ") || "Без имени";
              return (
                <div className={`compact-application-row ${reviewing ? "reviewing" : ""}`} key={item.id}>
                  <div className="compact-application-number">
                    <strong>#{item.id}</strong>
                    <span>{formatApplicationDate(item.created_at)}</span>
                  </div>
                  <div className="compact-applicant">
                    <strong>{displayName}</strong>
                    <span>
                      {item.user.username ? `@${item.user.username}` : `ID ${item.user.telegram_id}`}
                      {" · "}
                      {item.age ? `${item.age} лет` : "возраст не указан"}
                    </span>
                  </div>
                  <div className="compact-direction">
                    <span>{getApplicationDirectionTitle(item)}</span>
                    {item.status !== "pending" && <small className={`compact-status ${item.status}`}>{statusLabels[item.status] ?? item.status}</small>}
                  </div>
                  {reviewing && item.status === "pending" ? (
                    <textarea
                      className="compact-review-comment"
                      aria-label={`Комментарий пользователю по заявке №${item.id}`}
                      value={comments[item.id] ?? ""}
                      onChange={(event) => setComments((current) => ({ ...current, [item.id]: event.target.value }))}
                      rows={2}
                      placeholder="Комментарий пользователю (необязательно)"
                    />
                  ) : reviewing ? (
                    <div className="compact-resolution-summary">
                      <strong>{statusLabels[item.status] ?? item.status}</strong>
                      <span>{item.admin_comment || "Комментарий пользователю не оставлен"}</span>
                    </div>
                  ) : (
                    <div className="compact-work-files">
                      {item.files.length > 0 ? item.files.slice(0, 10).map((file) => {
                        const previewKind = getPreviewKind(file);
                        return (
                          <button
                            className="compact-work-file"
                            key={file.id}
                            title={`${file.file_name ?? fileTypeLabels[file.file_type] ?? "Вложение"}${file.file_size ? ` · ${formatFileSize(file.file_size)}` : ""}`}
                            onClick={() => openApplicationFile(item.id, file)}
                          >
                            {previewKind === "audio" ? <Play size={11} /> : previewKind ? <Eye size={11} /> : <FileText size={11} />}
                            <span>{file.file_name ?? fileTypeLabels[file.file_type] ?? "Вложение"}</span>
                          </button>
                        );
                      }) : <span className="compact-skipped">Пропущено</span>}
                    </div>
                  )}
                  <div className="compact-actions">
                    {!reviewing ? (
                      <button className="compact-action expand-action" title="Действия с заявкой" aria-label="Действия с заявкой" onClick={() => setReviewingApplicationId(item.id)}>
                        <MoreHorizontal size={17} />
                      </button>
                    ) : item.status === "pending" ? (
                      <>
                        <button className="compact-action approve" title="Принять" aria-label="Принять" onClick={() => void review(item.id, "approve")}><Check size={15} /></button>
                        <button className="compact-action reject" title="Отклонить" aria-label="Отклонить" onClick={() => void review(item.id, "reject")}><XCircle size={15} /></button>
                        <button className="compact-action ban-button" title="Заблокировать" aria-label="Заблокировать" onClick={() => void banApplication(item.id)}><ShieldBan size={15} /></button>
                        <button className="compact-action return-action" title="Вернуться" aria-label="Вернуться" onClick={() => setReviewingApplicationId(null)}><RotateCcw size={15} /></button>
                      </>
                    ) : (
                      <>
                        {["approved", "rejected"].includes(item.status) && <button className="compact-action" title="Повторить уведомление" aria-label="Повторить уведомление" onClick={() => void resendNotification(item.id)}><Send size={14} /></button>}
                        {item.status === "approved" && <button className="compact-action reject" title="Аннулировать" aria-label="Аннулировать" onClick={() => void annulApplication(item.id)}><RotateCcw size={15} /></button>}
                        {!item.user.is_banned && <button className="compact-action ban-button" title="Заблокировать" aria-label="Заблокировать" onClick={() => void banApplication(item.id)}><ShieldBan size={15} /></button>}
                        <button className="compact-action return-action" title="Вернуться" aria-label="Вернуться" onClick={() => setReviewingApplicationId(null)}><RotateCcw size={15} /></button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {activeTab === "participants" && (
        <section className="section-content">
          <div className="section-heading">
            <div><h2>Участники</h2><p>{participantSource === "group" ? "Пользователи, которых бот видел в группе" : "Пользователи, взаимодействовавшие с ботом"}</p></div>
            <span className="count">{filteredParticipants.length}</span>
          </div>
          <div className="application-filter-tabs participant-source-tabs" role="tablist" aria-label="Источник участников">
            <button className={participantSource === "group" ? "active" : ""} onClick={() => setParticipantSource("group")} role="tab" aria-selected={participantSource === "group"}>
              <span>Группа</span><em>{participantSourceCounts.group}</em>
            </button>
            <button className={participantSource === "bot" ? "active" : ""} onClick={() => setParticipantSource("bot")} role="tab" aria-selected={participantSource === "bot"}>
              <span>Бот</span><em>{participantSourceCounts.bot}</em>
            </button>
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

      {activeTab === "support" && (
        <section className="section-content">
          <div className="section-heading">
            <div><h2>Поддержка</h2><p>Обращения пользователей и переписка с администрацией</p></div>
            <span className="count">{supportTickets.filter((ticket) => ticket.status !== "closed").length}</span>
          </div>
          <div className="support-list">
            <div className="support-ticket-head-row">
              <span>Тикет</span><span>Пользователь</span><span>Первоначальный вопрос</span><span>Ответственный</span><span>Статус</span><span></span>
            </div>
            {supportTickets.map((ticket) => {
              const expanded = expandedSupportTicketId === ticket.id;
              const isAssignedToCurrent = ticket.assigned_admin?.id === currentAdmin?.id;
              const userName = [ticket.user.first_name, ticket.user.last_name].filter(Boolean).join(" ") || "Без имени";
              const userMeta = [
                ticket.user.username ? `@${ticket.user.username}` : null,
                `ID ${ticket.user.telegram_id}`,
              ].filter(Boolean).join(" · ");
              const assigneeName = ticket.assigned_admin
                ? [ticket.assigned_admin.first_name, ticket.assigned_admin.last_name].filter(Boolean).join(" ")
                  || (ticket.assigned_admin.username ? `@${ticket.assigned_admin.username}` : `ID ${ticket.assigned_admin.telegram_id}`)
                : null;
              const assigneeMeta = ticket.assigned_admin
                ? [
                    ticket.assigned_admin.username ? `@${ticket.assigned_admin.username}` : null,
                    `ID ${ticket.assigned_admin.telegram_id}`,
                  ].filter(Boolean).join(" · ")
                : "Свободный тикет";
              const initialQuestion = ticket.messages[0]?.text ?? "Без текста";
              return (
                <article className={`support-ticket ${expanded ? "expanded" : ""}`} key={ticket.id}>
                  <button
                    className="support-ticket-row"
                    type="button"
                    aria-expanded={expanded}
                    onClick={() => setExpandedSupportTicketId((current) => current === ticket.id ? null : ticket.id)}
                  >
                    <span className="support-ticket-number">
                      <strong>#{ticket.id}</strong>
                      <span>{formatApplicationDate(ticket.created_at)}</span>
                    </span>
                    <span className="support-ticket-user">
                      <strong>{userName}</strong>
                      <span>{userMeta}</span>
                    </span>
                    <span className="support-ticket-question">
                      <small>Первоначальный вопрос</small>
                      <strong>{initialQuestion}</strong>
                    </span>
                    <span className={`support-ticket-assignee ${ticket.assigned_admin ? "" : "unassigned"}`}>
                      <strong>{assigneeName ?? "Не назначен"}</strong>
                      <span>{assigneeMeta}</span>
                    </span>
                    <span className={`support-status ${ticket.status}`}>
                      {ticket.status === "open" ? "Новый" : ticket.status === "in_progress" ? "В работе" : "Закрыт"}
                    </span>
                    <span className="support-expand-icon">
                      {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                    </span>
                  </button>
                  {expanded && (
                    <div className="support-ticket-details">
                      <div className="support-thread">
                        {ticket.messages.map((message) => (
                          <div className={`support-message ${message.sender_type}`} key={message.id}>
                            <div>
                              <strong>
                                {message.sender_type === "user"
                                  ? userName
                                  : message.admin
                                    ? [message.admin.first_name, message.admin.last_name].filter(Boolean).join(" ")
                                      || (message.admin.username ? `@${message.admin.username}` : "Администратор")
                                    : "Администратор"}
                              </strong>
                              <time>{formatLogDate(message.created_at)}</time>
                            </div>
                            <p>{message.text}</p>
                          </div>
                        ))}
                      </div>
                      <div className="support-actions">
                        {ticket.status === "open" && !ticket.assigned_admin && (
                          <button className="approve" onClick={() => updateSupportTicket(ticket.id, "claim")}>
                            <UserCheck size={17} /> Взять тикет
                          </button>
                        )}
                        {ticket.status !== "closed" && isAssignedToCurrent && (
                          <>
                            <div className="support-reply">
                              <textarea
                                rows={3}
                                placeholder="Ответ пользователю"
                                value={supportReplyDrafts[ticket.id] ?? ""}
                                onChange={(event) => setSupportReplyDrafts((current) => ({
                                  ...current,
                                  [ticket.id]: event.target.value,
                                }))}
                              />
                              <button className="approve" onClick={() => replyToSupportTicket(ticket.id)}>
                                <Send size={17} /> Ответить
                              </button>
                            </div>
                            <button onClick={() => updateSupportTicket(ticket.id, "release")}>
                              <UserMinus size={17} /> Передать
                            </button>
                            <button className="reject" onClick={() => updateSupportTicket(ticket.id, "close")}>
                              <XCircle size={17} /> Закрыть
                            </button>
                          </>
                        )}
                        {ticket.status !== "closed" && ticket.assigned_admin && !isAssignedToCurrent && (
                          <span className="support-locked">Тикет находится в работе у другого сотрудника.</span>
                        )}
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
            {supportTickets.length === 0 && <div className="empty">Обращений пока нет.</div>}
          </div>
        </section>
      )}

      {activeTab === "settings" && hasFullAccess && (
        <section className="section-content">
          <nav className="settings-menu" aria-label="Разделы настроек">
            <button className={settingsSection === "topics" ? "active" : ""} onClick={() => setSettingsSection("topics")}>
              <Hash size={18} /><span><strong>Права тем</strong><small>Доступ к публикации</small></span>
            </button>
            <button className={settingsSection === "roles" ? "active" : ""} onClick={() => setSettingsSection("roles")}>
              <BadgeCheck size={18} /><span><strong>Роли</strong><small>Создание и изменение</small></span>
            </button>
            <button className={settingsSection === "questions" ? "active" : ""} onClick={() => setSettingsSection("questions")}>
              <ListChecks size={18} /><span><strong>Анкета</strong><small>Вопросы и порядок</small></span>
            </button>
            <button className={settingsSection === "access" ? "active" : ""} onClick={() => setSettingsSection("access")}>
              <UserCog size={18} /><span><strong>Доступ</strong><small>Администраторы и модераторы</small></span>
            </button>
          </nav>

          {settingsSection === "topics" && (
            <>
              <div className="section-heading">
                <div><h2>Права тем</h2><p>Роли, которым разрешено публиковать сообщения</p></div>
                <span className="count">{topics.length}</span>
              </div>
              <div className="topic-settings">
                <div className="topic-list" aria-label="Темы группы">
                  {topics.map((topic) => (
                    <button className={`topic-item ${selectedTopicId === topic.id ? "active" : ""}`} key={topic.id} onClick={() => setSelectedTopicId(topic.id)}>
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
                      <div className="editor-heading"><div><span>Настройка темы</span><strong>{selectedTopic.title}</strong></div><Hash size={22} /></div>
                      <label htmlFor={`topic-title-${selectedTopic.id}`}>Название в панели</label>
                      <input id={`topic-title-${selectedTopic.id}`} value={topicTitleDrafts[selectedTopic.id] ?? selectedTopic.title} onChange={(event) => setTopicTitleDrafts((current) => ({ ...current, [selectedTopic.id]: event.target.value }))} />
                      <div className="role-editor-heading"><strong>Кто может писать</strong><span>Если ничего не выбрано, писать могут все</span></div>
                      <div className="role-options">
                        {roles.map((role) => {
                          const checked = (topicRoleDrafts[selectedTopic.id] ?? []).includes(role.code);
                          return <label className={checked ? "selected" : ""} key={role.code}><input type="checkbox" checked={checked} onChange={() => toggleTopicRole(selectedTopic.id, role.code)} /><span className="check-box">{checked && <Check size={15} />}</span><span>{role.title}</span></label>;
                        })}
                      </div>
                      <button className="save-permissions" onClick={() => saveTopicPermissions(selectedTopic)}><Save size={17} /> Сохранить права</button>
                    </>
                  ) : <div className="editor-empty"><Settings size={28} /><span>Выберите тему для настройки</span></div>}
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
            </>
          )}

          {settingsSection === "roles" && (
            <>
              <div className="section-heading"><div><h2>Настройка ролей</h2><p>Роли участников и права доступа к темам</p></div><span className="count">{roles.length}</span></div>
              <div className="create-config-row">
                <input placeholder="Название новой роли" value={newRoleTitle} onChange={(event) => setNewRoleTitle(event.target.value)} />
                <button onClick={createRole}><Plus size={17} /> Добавить роль</button>
              </div>
              <div className="config-list">
                {roles.map((role) => (
                  <div className="config-row" key={role.code}>
                    <div className="config-index"><BadgeCheck size={18} /></div>
                    <input value={role.id === undefined ? role.title : roleTitleDrafts[role.id] ?? role.title} onChange={(event) => role.id !== undefined && setRoleTitleDrafts((current) => ({ ...current, [role.id!]: event.target.value }))} />
                    <code>{role.code}</code>
                    <div className="config-actions">
                      <button className="icon-button" onClick={() => saveRole(role)} title="Сохранить роль"><Save size={17} /></button>
                      <button className="icon-button danger-icon" onClick={() => deleteRole(role)} title="Удалить роль"><Trash2 size={17} /></button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {settingsSection === "questions" && (
            <>
              <div className="section-heading"><div><h2>Настройка анкеты</h2><p>Варианты ответа могут вести к разным следующим вопросам</p></div><span className="count">{questions.length}</span></div>
              <div className="question-create">
                <input placeholder="Текст нового вопроса" value={newQuestionText} onChange={(event) => setNewQuestionText(event.target.value)} />
                <input placeholder="Подсказка пользователю (необязательно)" value={newQuestionHelp} onChange={(event) => setNewQuestionHelp(event.target.value)} />
                <select value={newQuestionType} onChange={(event) => setNewQuestionType(event.target.value as Question["answer_type"])}><option value="text">Текст</option><option value="number">Число</option><option value="single_choice">Один вариант</option><option value="file">Файл</option></select>
                <button onClick={createQuestion}><Plus size={17} /> Добавить</button>
              </div>
              <div className="question-list">
                {questions.map((question, index) => {
                  const draft = questionDrafts[question.id] ?? question;
                  return (
                    <article className="question-row" key={question.id}>
                      <div className="question-main-row">
                        <div className="question-order"><strong>{index + 1}</strong><button className="icon-button" disabled={index === 0} onClick={() => moveQuestion(question.id, -1)} title="Поднять"><ArrowUp size={16} /></button><button className="icon-button" disabled={index === questions.length - 1} onClick={() => moveQuestion(question.id, 1)} title="Опустить"><ArrowDown size={16} /></button></div>
                        <div className="question-fields">
                          <input value={draft.text} onChange={(event) => setQuestionDrafts((current) => ({ ...current, [question.id]: { ...draft, text: event.target.value } }))} />
                          <input placeholder="Подсказка" value={draft.help_text ?? ""} onChange={(event) => setQuestionDrafts((current) => ({ ...current, [question.id]: { ...draft, help_text: event.target.value } }))} />
                        </div>
                        <select value={draft.answer_type} onChange={(event) => changeQuestionType(draft, event.target.value as Question["answer_type"])}><option value="text">Текст</option><option value="number">Число</option><option value="single_choice">Один вариант</option><option value="file">Файл</option></select>
                        <div className="config-actions"><button className="icon-button" onClick={() => saveQuestion(question.id)} title="Сохранить вопрос"><Save size={17} /></button><button className="icon-button danger-icon" onClick={() => deleteQuestion(question)} title="Удалить вопрос"><Trash2 size={17} /></button></div>
                      </div>
                      <div className="question-transition">
                        <label>После ответа</label>
                        <select value={draft.next_question_code ?? ""} onChange={(event) => setQuestionDrafts((current) => ({ ...current, [question.id]: { ...draft, next_question_code: event.target.value || null } }))}>
                          <option value="">Следующий по порядку</option>
                          <option value="__end__">Завершить вопросы</option>
                          {questions.filter((item) => item.code !== question.code).map((item) => <option key={item.code} value={item.code}>{questions.findIndex((candidate) => candidate.code === item.code) + 1}. {item.text}</option>)}
                        </select>
                      </div>
                      {draft.answer_type === "single_choice" && (
                        <div className="question-options-editor">
                          <div className="question-options-heading"><strong>Варианты ответа</strong><span>Для каждого можно переопределить следующий вопрос</span></div>
                          {draft.options.map((option, optionIndex) => (
                            <div className="question-option-row" key={option.id}>
                              <span>{optionIndex + 1}</span>
                              <input placeholder="Название варианта" value={option.label} onChange={(event) => updateQuestionOption(draft, option.id, { label: event.target.value })} />
                              <select value={option.next_question_code ?? ""} onChange={(event) => updateQuestionOption(draft, option.id, { next_question_code: event.target.value || null })}>
                                <option value="">Как в «После ответа»</option>
                                <option value="__end__">Завершить вопросы</option>
                                {questions.filter((item) => item.code !== question.code).map((item) => <option key={item.code} value={item.code}>{questions.findIndex((candidate) => candidate.code === item.code) + 1}. {item.text}</option>)}
                              </select>
                              <button className="icon-button danger-icon" onClick={() => removeQuestionOption(draft, option.id)} title="Удалить вариант" aria-label="Удалить вариант"><Trash2 size={16} /></button>
                            </div>
                          ))}
                          <button className="add-option-button" onClick={() => addQuestionOption(draft)} disabled={draft.options.length >= 20}><Plus size={16} /> Добавить вариант</button>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </>
          )}

          {settingsSection === "access" && (
            <>
              <div className="section-heading">
                <div><h2>Доступ к панели</h2><p>Администраторы видят все разделы, модераторы — заявки и участников</p></div>
                <span className="count">{staff.length}</span>
              </div>
              <div className="staff-create">
                <input
                  inputMode="numeric"
                  placeholder="Telegram ID"
                  value={newStaffTelegramId}
                  onChange={(event) => setNewStaffTelegramId(event.target.value)}
                />
                <select value={newStaffRole} onChange={(event) => setNewStaffRole(event.target.value as "admin" | "moderator")}>
                  <option value="moderator">Модератор</option>
                  <option value="admin">Администратор</option>
                </select>
                <button onClick={addStaffMember}><Plus size={17} /> Выдать доступ</button>
              </div>
              <div className="staff-list">
                {staff.map((staffMember) => {
                  const isProtected = staffMember.role === "owner" || staffMember.id === currentAdmin?.id;
                  const name = [staffMember.first_name, staffMember.last_name].filter(Boolean).join(" ") || "Имя не сохранено";
                  return (
                    <div className="staff-row" key={staffMember.id}>
                      <div className="staff-identity">
                        <strong>{name}</strong>
                        <span>{staffMember.username ? `@${staffMember.username}` : "Без username"}</span>
                      </div>
                      <code>ID {staffMember.telegram_id}</code>
                      {staffMember.role === "owner" ? (
                        <span className="access-role">Владелец</span>
                      ) : (
                        <select
                          value={staffRoleDrafts[staffMember.id] ?? staffMember.role}
                          disabled={isProtected}
                          onChange={(event) => setStaffRoleDrafts((current) => ({
                            ...current,
                            [staffMember.id]: event.target.value as "admin" | "moderator",
                          }))}
                        >
                          <option value="moderator">Модератор</option>
                          <option value="admin">Администратор</option>
                        </select>
                      )}
                      <div className="config-actions">
                        {!isProtected && <button className="icon-button" onClick={() => saveStaffRole(staffMember)} title="Сохранить уровень доступа"><Save size={17} /></button>}
                        {!isProtected && <button className="icon-button danger-icon" onClick={() => revokeStaffAccess(staffMember)} title="Отозвать доступ"><Trash2 size={17} /></button>}
                        {isProtected && <span className="protected-access">Защищено</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </section>
      )}

      {activeTab === "bot" && hasFullAccess && (
        <section className="section-content">
          <div className="section-heading">
            <div><h2>Настройка бота</h2><p>Профиль Telegram и сообщения пользователям</p></div>
            <span className="count">{botMessages.length}</span>
          </div>

          {botProfileDraft && (
            <div className="bot-profile-settings">
              <div className="bot-avatar-column">
                <div className="bot-avatar-preview">
                  {botAvatarUrl ? <img src={botAvatarUrl} alt="Аватар бота" /> : <BotIcon size={42} />}
                </div>
                <strong>{botProfileDraft.name}</strong>
                <span>{botProfileDraft.username ? `@${botProfileDraft.username}` : `ID ${botProfileDraft.id}`}</span>
                <input
                  ref={avatarInputRef}
                  className="hidden-file-input"
                  type="file"
                  accept="image/jpeg,.jpg,.jpeg"
                  onChange={uploadBotAvatar}
                />
                <div className="avatar-actions">
                  <button onClick={() => avatarInputRef.current?.click()}><Camera size={17} /> Заменить</button>
                  <button className="icon-button danger-icon" disabled={!botProfile?.avatar_id} onClick={removeBotAvatar} title="Удалить аватар" aria-label="Удалить аватар"><Trash2 size={17} /></button>
                </div>
              </div>
              <div className="bot-profile-fields">
                <label>Имя бота<input maxLength={64} value={botProfileDraft.name} onChange={(event) => setBotProfileDraft({ ...botProfileDraft, name: event.target.value })} /></label>
                <label>Краткое описание<textarea maxLength={120} value={botProfileDraft.short_description} onChange={(event) => setBotProfileDraft({ ...botProfileDraft, short_description: event.target.value })} /></label>
                <label>Полное описание<textarea maxLength={512} value={botProfileDraft.description} onChange={(event) => setBotProfileDraft({ ...botProfileDraft, description: event.target.value })} /></label>
                <button className="save-permissions" onClick={saveBotProfile}><Save size={17} /> Сохранить профиль</button>
              </div>
            </div>
          )}

          <div className="bot-texts-heading">
            <div><h3>Сообщения бота</h3><p>Тексты применяются сразу после сохранения</p></div>
          </div>
          {botMessageCategories.map((category) => (
            <section className="bot-message-group" key={category}>
              <h3>{category}</h3>
              <div className="bot-message-list">
                {botMessages.filter((item) => item.category === category).map((item) => (
                  <article className="bot-message-row" key={item.key}>
                    <div className="bot-message-meta">
                      <div><strong>{item.title}</strong><span className={item.is_custom ? "custom-text-status" : "default-text-status"}>{item.is_custom ? "Изменен" : "Исходный"}</span></div>
                      <p>{item.description}</p>
                      {item.variables.length > 0 && <div className="template-variables">{item.variables.map((variable) => <code key={variable}>{`{${variable}}`}</code>)}</div>}
                    </div>
                    <textarea value={botMessageDrafts[item.key] ?? item.text} onChange={(event) => setBotMessageDrafts((current) => ({ ...current, [item.key]: event.target.value }))} />
                    <div className="bot-message-actions">
                      <button className="icon-button" disabled={!item.is_custom} onClick={() => resetBotText(item)} title="Вернуть исходный текст" aria-label="Вернуть исходный текст"><RotateCcw size={17} /></button>
                      <button className="icon-button" onClick={() => saveBotText(item.key)} title="Сохранить текст" aria-label="Сохранить текст"><Save size={17} /></button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </section>
      )}

      {activeTab === "logs" && hasFullAccess && (
        <section className="section-content">
          <div className="section-heading"><div><h2>Логи</h2><p>События бота, пользователей и администрации</p></div><span className="count">{logs.length}</span></div>
          <div className="bot-status-bar">
            <Activity size={20} />
            <div><strong>Telegram API</strong><span>{botStatus?.username ? `@${botStatus.username}` : "Бот недоступен"} · режим {botStatus?.mode ?? "polling"}</span></div>
            <em className={botStatus?.telegram_api ? "online" : "offline"}>{botStatus?.telegram_api ? "Доступен" : "Ошибка"}</em>
          </div>
          <div className="audit-list">
            {logs.map((entry) => (
              <div className="audit-row" key={entry.id}>
                <time>{formatLogDate(entry.created_at)}</time>
                <div><strong>{auditActionLabels[entry.action] ?? entry.action}</strong><span>{formatActor(entry)} · {entry.entity_type}{entry.entity_id ? ` #${entry.entity_id}` : ""}</span></div>
                <code>{Object.keys(entry.payload).length > 0 ? JSON.stringify(entry.payload) : "—"}</code>
              </div>
            ))}
            {logs.length === 0 && <div className="empty">Событий пока нет.</div>}
          </div>
        </section>
      )}

      {previewFile && activePreviewKind === "audio" && (
        <section className="audio-player-dock" aria-label={`Аудиоплеер: ${previewFile.file.file_name ?? "Вложение"}`}>
          <audio
            ref={audioPlayerRef}
            src={activePreviewUrl ?? undefined}
            preload="metadata"
            onLoadedMetadata={(event) => setAudioDuration(event.currentTarget.duration)}
            onDurationChange={(event) => setAudioDuration(event.currentTarget.duration)}
            onTimeUpdate={(event) => setAudioCurrentTime(event.currentTarget.currentTime)}
            onPlay={() => setAudioPlaying(true)}
            onPause={() => setAudioPlaying(false)}
            onEnded={() => setAudioPlaying(false)}
          />
          <button
            className="audio-player-control primary"
            disabled={!activePreviewUrl}
            onClick={toggleAudioPlayback}
            title={audioPlaying ? "Пауза" : "Воспроизвести"}
            aria-label={audioPlaying ? "Пауза" : "Воспроизвести"}
          >
            {audioPlaying ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <div className="audio-player-track">
            <strong>{previewFile.file.file_name ?? fileTypeLabels[previewFile.file.file_type] ?? "Вложение"}</strong>
            <span>
              Заявка #{previewFile.applicationId}
              {previewUserName ? ` · ${previewUserName}` : ""}
              {previewFile.file.file_size ? ` · ${formatFileSize(previewFile.file.file_size)}` : ""}
            </span>
          </div>
          <div className="audio-player-timeline">
            <span>{formatMediaTime(audioCurrentTime)}</span>
            <input
              type="range"
              min="0"
              max={safeAudioDuration}
              step="0.1"
              value={Math.min(audioCurrentTime, safeAudioDuration)}
              disabled={!safeAudioDuration}
              onChange={(event) => seekAudio(Number(event.target.value))}
              aria-label="Позиция воспроизведения"
            />
            <span>{formatMediaTime(safeAudioDuration)}</span>
          </div>
          <label className="audio-player-volume">
            <Volume2 size={16} />
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={audioVolume}
              onChange={(event) => changeAudioVolume(Number(event.target.value))}
              aria-label="Громкость"
            />
          </label>
          {previewFile.file.url ? (
            <a className="audio-player-control" href={previewFile.file.url} target="_blank" rel="noreferrer" title="Скачать" aria-label="Скачать">
              <Download size={16} />
            </a>
          ) : (
            <button className="audio-player-control" onClick={() => void downloadFile(previewFile.applicationId, previewFile.file)} title="Скачать" aria-label="Скачать">
              <Download size={16} />
            </button>
          )}
          <button className="audio-player-control" onClick={closeApplicationPreview} title="Закрыть" aria-label="Закрыть">
            <XCircle size={17} />
          </button>
          {loadingPreviews.has(previewFile.file.id) && <span className="audio-player-loading">Подготовка потока...</span>}
        </section>
      )}

      {previewFile && activePreviewKind !== "audio" && (
        <div className="file-preview-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeApplicationPreview();
        }}>
          <section className="file-preview-dialog" role="dialog" aria-modal="true" aria-label={previewFile.file.file_name ?? "Предпросмотр вложения"}>
            <header>
              <div>
                <strong>{previewFile.file.file_name ?? fileTypeLabels[previewFile.file.file_type] ?? "Вложение"}</strong>
                <span>
                  {fileTypeLabels[previewFile.file.file_type] ?? previewFile.file.file_type}
                  {previewFile.file.file_size ? ` · ${formatFileSize(previewFile.file.file_size)}` : ""}
                </span>
              </div>
              <div className="file-preview-actions">
                {previewFile.file.url ? (
                  <a className="icon-button" href={previewFile.file.url} target="_blank" rel="noreferrer" title="Открыть отдельно" aria-label="Открыть отдельно"><ExternalLink size={16} /></a>
                ) : (
                  <button className="icon-button" onClick={() => void downloadFile(previewFile.applicationId, previewFile.file)} title="Скачать" aria-label="Скачать"><Download size={16} /></button>
                )}
                <button className="icon-button" onClick={closeApplicationPreview} title="Закрыть" aria-label="Закрыть"><XCircle size={17} /></button>
              </div>
            </header>
            <div className="file-preview-content">
              {loadingPreviews.has(previewFile.file.id) && <div className="loading-line">Загрузка предпросмотра...</div>}
              {activePreviewUrl && activePreviewKind === "video" && <video controls autoPlay src={activePreviewUrl} />}
              {activePreviewUrl && activePreviewKind === "image" && <img src={activePreviewUrl} alt={previewFile.file.file_name ?? "Вложение"} />}
              {activePreviewUrl && activePreviewKind === "pdf" && <iframe src={activePreviewUrl} title={previewFile.file.file_name ?? "PDF"} />}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
