CREATE TABLE `visitor_rate_events` (
	`id` text PRIMARY KEY NOT NULL,
	`occurred_at` integer NOT NULL,
	`ip_address` text
);
--> statement-breakpoint
CREATE INDEX `visitor_rate_time` ON `visitor_rate_events` (`occurred_at`);--> statement-breakpoint
CREATE INDEX `visitor_rate_ip_time` ON `visitor_rate_events` (`ip_address`,`occurred_at`);