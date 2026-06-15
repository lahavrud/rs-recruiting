/** Mirrors backend AuditLogRead schema. */
export interface AuditLogRead {
  id: number;
  actor_user_id: number | null;
  action: string;
  target_type: string;
  target_id: number;
  detail: string | null;
  ip_address: string | null;
  created_at: string;
}
