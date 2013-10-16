BEGIN;
CREATE TABLE `nonamo_addon_authors` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `nonamoaddon_id` varchar(255) NOT NULL,
    `userprofile_id` integer NOT NULL,
    UNIQUE (`nonamoaddon_id`, `userprofile_id`)
)
;
ALTER TABLE `nonamo_addon_authors`
ADD CONSTRAINT `nonamo_addon_authors_userprofile_id`
FOREIGN KEY (`userprofile_id`)
REFERENCES `users` (`id`);

CREATE TABLE `nonamo_addon` (
    `guid` varchar(255) NOT NULL PRIMARY KEY,
    `name` varchar(255) NOT NULL,
    `description` varchar(500) NOT NULL
);

ALTER TABLE `nonamo_addon_authors`
ADD CONSTRAINT `nonamo_addon_authors_nonamoaddon_id`
FOREIGN KEY (`nonamoaddon_id`)
REFERENCES `nonamo_addon` (`guid`);

CREATE TABLE `nonamo_addon_hashes` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `created` datetime NOT NULL,
    `modified` datetime NOT NULL,
    `addon_id` varchar(255) NOT NULL,
    `sha256` varchar(64) NOT NULL UNIQUE,
    `registered` bool NOT NULL,
    `version` varchar(255) NOT NULL
);

ALTER TABLE `nonamo_addon_hashes`
ADD CONSTRAINT `nonamo_addon_hashes_addonid`
FOREIGN KEY (`addon_id`)
REFERENCES `nonamo_addon` (`guid`);

CREATE INDEX `nonamo_addon_hashes_cc3d5937` ON `nonamo_addon_hashes` (`addon_id`);
COMMIT;
