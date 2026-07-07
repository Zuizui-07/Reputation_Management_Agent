-- ================================================
--  Reputation Management Agent — Database Schema
--  Run against: reputation_agent_db
-- ================================================

-- Create the database (if it doesn't exist)
CREATE DATABASE IF NOT EXISTS `reputation_agent_db`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE `reputation_agent_db`;


-- ──────────────────────────────────────────────
--  1. Users Table (Admin dashboard access)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `users` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `email`         VARCHAR(255) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role`          ENUM('superadmin') NOT NULL DEFAULT 'superadmin',
    `created_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX `idx_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ──────────────────────────────────────────────
--  2. Messages Table (DMs from FB / IG)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `messages` (
    `id`              INT AUTO_INCREMENT PRIMARY KEY,
    `platform`        ENUM('facebook', 'instagram','google_reviews','reddit') NOT NULL,
    `platform_msg_id` VARCHAR(255) NOT NULL UNIQUE,
    `sender_id`       VARCHAR(255) NOT NULL,
    `sender_name`     VARCHAR(255) DEFAULT NULL,
    `content`         TEXT NOT NULL,
    `thread_id`       VARCHAR(255) DEFAULT NULL,
    `received_at`     DATETIME NOT NULL,
    `created_at`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX `idx_messages_platform_msg_id` (`platform_msg_id`),
    INDEX `idx_messages_platform` (`platform`),
    INDEX `idx_messages_received_at` (`received_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ──────────────────────────────────────────────
--  3. Classifications Table (Groq LLM intent)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `classifications` (
    `id`               INT AUTO_INCREMENT PRIMARY KEY,
    `message_id`       INT NOT NULL,
    `intent`           ENUM(
                          'potential_lead',
                          'customer_support',
                          'general_inquiry',
                          'sensitive_complaint',
                          'partnership_inquiry',
                          'spam'
                       ) NOT NULL,
    `confidence`       FLOAT NOT NULL,
    `raw_llm_response` TEXT DEFAULT NULL,
    `classified_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX `idx_classifications_message_id` (`message_id`),
    INDEX `idx_classifications_intent` (`intent`),

    CONSTRAINT `fk_classifications_message`
        FOREIGN KEY (`message_id`) REFERENCES `messages`(`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ──────────────────────────────────────────────
--  4. Drafted Replies Table (Groq LLM drafts)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `drafted_replies` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `message_id`   INT NOT NULL,
    `content`      TEXT NOT NULL,
    `generated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `model_used`   VARCHAR(100) DEFAULT NULL,

    INDEX `idx_drafted_replies_message_id` (`message_id`),

    CONSTRAINT `fk_drafted_replies_message`
        FOREIGN KEY (`message_id`) REFERENCES `messages`(`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ──────────────────────────────────────────────
--  5. Actions Table (Full audit trail)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `actions` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `message_id`   INT NOT NULL,
    `action_type`  ENUM(
                      'received',
                      'classified',
                      'draft_generated',
                      'auto_sent',
                      'escalated',
                      'approved',
                      'rejected',
                      'edited_and_approved'
                   ) NOT NULL,
    `actor`        VARCHAR(100) DEFAULT NULL,
    `final_reply`  TEXT DEFAULT NULL,
    `performed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX `idx_actions_message_id` (`message_id`),
    INDEX `idx_actions_action_type` (`action_type`),
    INDEX `idx_actions_performed_at` (`performed_at`),

    CONSTRAINT `fk_actions_message`
        FOREIGN KEY (`message_id`) REFERENCES `messages`(`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ══════════════════════════════════════════════
--  Schema creation complete.
--  Run SHOW TABLES; and DESCRIBE <table>; manually to verify.
-- ══════════════════════════════════════════════
