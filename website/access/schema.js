import { sqliteTable, text, integer, index } from "drizzle-orm/sqlite-core";

export const visitors = sqliteTable("approved_visitors", {
  email: text().primaryKey(), name: text().notNull(), enabled: integer().notNull().default(1),
});
export const sessions = sqliteTable("visitor_sessions", {
  token_hash: text().primaryKey(), email: text().notNull().references(() => visitors.email),
  created_at: integer().notNull(), expires_at: integer().notNull(),
  timezone: text(), utc_offset_minutes: integer(), language: text(),
}, (t) => [index("session_expiration").on(t.expires_at)]);
export const events = sqliteTable("visit_events", {
  id: text().primaryKey(), email: text(), occurred_at: integer().notNull(),
  kind: text().notNull(), outcome: text().notNull(), path: text().notNull(),
  timezone: text(), utc_offset_minutes: integer(), language: text(), accept_language: text(),
  ip_address: text(), context_hash: text(),
}, (t) => [index("visit_time").on(t.occurred_at), index("attempt_ip_time").on(t.ip_address, t.occurred_at)]);
export const settings = sqliteTable("access_settings", {
  key: text().primaryKey(), value: text().notNull(),
});
export const rateEvents = sqliteTable("visitor_rate_events", {
  id: text().primaryKey(), occurred_at: integer().notNull(), ip_address: text(),
}, (t) => [index("visitor_rate_time").on(t.occurred_at), index("visitor_rate_ip_time").on(t.ip_address, t.occurred_at)]);
