CREATE TABLE `season` (
  `id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '赛季，用年份表示，例如2024，2025',
  `is_current_season` tinyint DEFAULT '0' COMMENT '0表示这个赛季不是当前赛季，1表示这个赛季是当前赛季',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='赛季表，记录所有赛季，且是否是当前赛季，同时只能有一个is_current_season为1'