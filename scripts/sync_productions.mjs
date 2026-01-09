#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const DEFAULT_CANDIDATES_PATH = "data/production_candidates.json";
const DEFAULT_OUTPUT_PATH = "docs/data/productions.json";

const parseArgs = (argv) => {
  const args = new Map();
  const flags = new Set();
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg.startsWith("--")) {
      const name = arg.slice(2);
      const next = argv[index + 1];
      if (!next || next.startsWith("--")) {
        flags.add(name);
      } else {
        args.set(name, next);
        index += 1;
      }
    }
  }
  return { args, flags };
};

const parseLimit = (value) => {
  if (value === undefined) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed <= 0) {
    throw new Error(`Invalid --limit value: ${value}`);
  }
  return parsed;
};

const readJson = async (filePath) => {
  const raw = await fs.readFile(filePath, "utf8");
  return JSON.parse(raw);
};

const areArraysEqual = (left = [], right = []) => {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((value, index) => value === right[index]);
};

const normalizeRecord = (record) => JSON.parse(JSON.stringify(record));

const main = async () => {
  const { args, flags } = parseArgs(process.argv.slice(2));
  const candidatesPath = args.get("candidates") || DEFAULT_CANDIDATES_PATH;
  const outputPath = args.get("output") || DEFAULT_OUTPUT_PATH;
  const limit = parseLimit(args.get("limit"));
  const dryRun = flags.has("dry-run");

  const resolvedCandidatesPath = path.resolve(candidatesPath);
  const resolvedOutputPath = path.resolve(outputPath);

  const candidates = await readJson(resolvedCandidatesPath);
  const productions = await readJson(resolvedOutputPath);

  if (!Array.isArray(candidates)) {
    throw new Error("Candidates file must contain an array.");
  }
  if (!Array.isArray(productions)) {
    throw new Error("Productions file must contain an array.");
  }

  const totalCandidates = candidates.length;
  const limitedCandidates = limit ? candidates.slice(0, limit) : candidates;

  const productionIndex = new Map();
  productions.forEach((production, index) => {
    if (production.id) {
      productionIndex.set(production.id, index);
    }
  });

  let createdCount = 0;
  let updatedCount = 0;
  let themesUnchangedCount = 0;
  let themeMismatchCount = 0;

  limitedCandidates.forEach((candidate) => {
    if (!candidate || typeof candidate !== "object") {
      return;
    }

    const { id } = candidate;
    if (!id) {
      return;
    }

    const existingIndex = productionIndex.get(id);
    if (existingIndex === undefined) {
      productions.push(candidate);
      createdCount += 1;
      return;
    }

    const existing = productions[existingIndex];
    const existingThemes = existing.themes || [];
    const candidateThemes = candidate.themes || [];
    if (!areArraysEqual(existingThemes, candidateThemes)) {
      themeMismatchCount += 1;
    }

    const merged = {
      ...existing,
      ...candidate,
      themes: existingThemes,
    };

    if (areArraysEqual(existingThemes, merged.themes || [])) {
      themesUnchangedCount += 1;
    }

    const normalizedExisting = normalizeRecord(existing);
    const normalizedMerged = normalizeRecord(merged);
    const hasChanges =
      JSON.stringify(normalizedExisting) !== JSON.stringify(normalizedMerged);

    if (hasChanges) {
      productions[existingIndex] = merged;
      updatedCount += 1;
    }
  });

  console.log(`Candidates found: ${totalCandidates}`);
  if (limit) {
    console.log(`Candidates processed (limit ${limit}): ${limitedCandidates.length}`);
  }
  console.log(`Productions created: ${createdCount}`);
  console.log(`Productions updated: ${updatedCount}`);
  console.log(`Existing themes unchanged: ${themesUnchangedCount}`);
  if (themeMismatchCount > 0) {
    console.log(
      `Theme mismatches detected: ${themeMismatchCount} (kept existing themes)`
    );
  }

  if (dryRun) {
    console.log("Dry run enabled; no files were written.");
    return;
  }

  await fs.writeFile(
    resolvedOutputPath,
    `${JSON.stringify(productions, null, 2)}\n`,
    "utf8"
  );
};

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
