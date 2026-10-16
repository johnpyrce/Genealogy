CREATE TABLE `visit_events` (
	`id` text PRIMARY KEY NOT NULL,
	`email` text,
	`occurred_at` integer NOT NULL,
	`kind` text NOT NULL,
	`outcome` text NOT NULL,
	`path` text NOT NULL,
	`timezone` text,
	`utc_offset_minutes` integer,
	`language` text,
	`accept_language` text,
	`ip_address` text,
	`context_hash` text
);
--> statement-breakpoint
CREATE INDEX `visit_time` ON `visit_events` (`occurred_at`);--> statement-breakpoint
CREATE INDEX `attempt_ip_time` ON `visit_events` (`ip_address`,`occurred_at`);--> statement-breakpoint
CREATE TABLE `visitor_sessions` (
	`token_hash` text PRIMARY KEY NOT NULL,
	`email` text NOT NULL,
	`created_at` integer NOT NULL,
	`expires_at` integer NOT NULL,
	`timezone` text,
	`utc_offset_minutes` integer,
	`language` text,
	FOREIGN KEY (`email`) REFERENCES `approved_visitors`(`email`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `session_expiration` ON `visitor_sessions` (`expires_at`);--> statement-breakpoint
CREATE TABLE `access_settings` (
	`key` text PRIMARY KEY NOT NULL,
	`value` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `approved_visitors` (
	`email` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`enabled` integer DEFAULT 1 NOT NULL
);
