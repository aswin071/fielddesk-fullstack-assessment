export type Role = "owner" | "dispatcher" | "technician";

export interface Session {
  user: { id: string; email: string; firstName: string; lastName: string; fullName: string };
  role: Role;
  organisation: { id: string; name: string; slug: string };
}

export interface Person {
  id: string;
  userId: string;
  fullName: string;
  email: string;
  role: Role;
}

export interface OrganisationUser extends Person {
  firstName: string;
  lastName: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface WorkOrder {
  id: string;
  referenceNumber: string;
  title: string;
  description: string;
  priority: "low" | "medium" | "high" | "urgent";
  status: "draft" | "scheduled" | "in_progress" | "blocked" | "completed" | "cancelled";
  assignedTechnician: Person | null;
  scheduledStart: string | null;
  scheduledEnd: string | null;
  siteName: string;
  creator: Person;
  createdAt: string;
  updatedAt: string;
}

export interface Attachment {
  id: string;
  fileName: string;
  contentType: string;
  sizeBytes: number;
  checksumSha256: string;
  uploadedBy: string;
  createdAt: string;
  downloadUrl: string;
}

export interface AuditEntry {
  id: string;
  action: string;
  targetType: string;
  targetId: string;
  actor: { id: string; name: string; role: Role } | null;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  metadata: Record<string, unknown>;
  correlationId: string;
  createdAt: string;
}

export interface DashboardSummary {
  total: number;
  assigned: number;
  unassigned: number;
  byStatus: Record<WorkOrder["status"], number>;
  byPriority: Record<WorkOrder["priority"], number>;
}

export interface Organisation {
  id: string;
  name: string;
  slug: string;
  storageLimitBytes: number;
  storageUsedBytes: number;
  createdAt: string;
  updatedAt: string;
}

export interface Page<T> {
  data: T[];
  meta: { page: number; pageSize: number; total: number; totalPages: number };
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    fields: Record<string, string[] | Record<string, string[]>>;
    correlationId?: string;
  };
}
