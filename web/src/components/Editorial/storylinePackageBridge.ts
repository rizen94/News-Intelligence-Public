/**
 * Storyline → editorial_package handoff helpers (v11 modal bridge).
 */
import { editorialApi, type ModalKey } from '@/services/api/editorial';
import { unwrapData } from '@/services/api/editorialUnwrap';

const RESEARCH_DOMAINS = new Set([
  'medicine',
  'neurodiversity',
  'artificial-intelligence',
]);

const NARRATIVE_DOMAINS = new Set(['politics', 'finance', 'legal']);

export function legacySeedForStoryline(
  domainKey: string,
  storylineId: number | string
): string {
  return `storyline:${domainKey}:${Number(storylineId)}`;
}

/** Prefer Research or Narrative rail for the domain tag. */
export function defaultModalForDomain(domainKey: string): ModalKey {
  if (RESEARCH_DOMAINS.has(domainKey)) return 'research';
  if (NARRATIVE_DOMAINS.has(domainKey)) return 'narrative';
  return 'narrative';
}

/** Workspace path for a modal + package (Editor uses package detail). */
export function modalPackagePath(
  domainKey: string,
  modal: ModalKey,
  packageId: number
): string {
  if (modal === 'editor') {
    return `/${domainKey}/editor/packages/${packageId}`;
  }
  return `/${domainKey}/${modal}?package=${packageId}`;
}

export type StorylinePackageResult = {
  id: number;
  created?: boolean;
  legacy_seed?: string;
  suggested_modal?: string;
  working_title?: string;
};

/** Find or create editorial_package for a storyline; returns package id. */
export async function ensurePackageForStoryline(opts: {
  domainKey: string;
  storylineId: number | string;
  targetModal?: ModalKey;
  refreshMembers?: boolean;
}): Promise<StorylinePackageResult> {
  const res = await editorialApi.fromStoryline({
    domain_key: opts.domainKey,
    storyline_id: Number(opts.storylineId),
    target_modal: opts.targetModal,
    refresh_members: opts.refreshMembers,
    actor: 'operator',
  });
  const data = unwrapData<StorylinePackageResult>(res);
  const id = Number(data?.id);
  if (!id) throw new Error('No package id returned from from_storyline');
  return { ...data, id };
}
