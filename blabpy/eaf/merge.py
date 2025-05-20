import copy
from .eaf_tree import EafTree, Annotation, ExternalReference, ControlledVocabulary, ControlledVocabularyEntry, LinguisticType


def _tiers_equal(t1, t2):
    """Compare two tiers for equality of linguistic type, participant, and parent_ref."""
    return (
        t1.linguistic_type_ref == t2.linguistic_type_ref and
        t1.participant == t2.participant and
        t1.parent_ref == t2.parent_ref)


def _annotations_equal(a1, a2):
    """Compare two annotations: alignable by onset/offset/value, reference by annotation_ref/value."""
    if a1.annotation_type != a2.annotation_type:
        return False
    if a1.annotation_type == Annotation.ALIGNABLE_ANNOTATION:
        return (
            a1.onset == a2.onset and
            a1.offset == a2.offset and
            a1.value == a2.value)
    else:  # REF_ANNOTATION
        return (
            a1.annotation_ref == a2.annotation_ref and
            a1.value == a2.value)


def _external_references_equal(er1: ExternalReference, er2: ExternalReference):
    """Compare two ExternalReference objects for equality of type and value."""
    return (
        er1.type == er2.type and
        er1.value == er2.value)


def _cv_entries_equal(cve1: ControlledVocabularyEntry, cve2: ControlledVocabularyEntry):
    """Compare two ControlledVocabularyEntry objects for equality of description and value."""
    # Note: CVE_ID is the key for the dictionary, so it's implicitly compared by structure.
    return (
        cve1.description == cve2.description and
        cve1.value == cve2.value)


def _controlled_vocabularies_equal(cv1: ControlledVocabulary, cv2: ControlledVocabulary):
    """Compare two ControlledVocabulary objects."""
    if cv1.ext_ref != cv2.ext_ref:
        return False
    
    # Both have same ext_ref (either both None or both same string)
    if cv1.ext_ref is None: # Internal CV definition
        if cv1.description != cv2.description: # Compare text of DESCRIPTION element
            return False
        if set(cv1.entries.keys()) != set(cv2.entries.keys()):
            return False
        for cve_id in cv1.entries:
            if not _cv_entries_equal(cv1.entries[cve_id], cv2.entries[cve_id]):
                return False
    # If ext_ref is not None, equality of ext_ref string is sufficient as content comes from external source.
    return True


def _linguistic_types_equal(lt1: LinguisticType, lt2: LinguisticType):
    """Compare two LinguisticType objects."""
    return (
        lt1.time_alignable == lt2.time_alignable and
        lt1.graphic_references == lt2.graphic_references and
        lt1.constraints == lt2.constraints and
        lt1.controlled_vocabulary_ref == lt2.controlled_vocabulary_ref)


def _collect_base_divergences(base: EafTree, ours: EafTree, theirs: EafTree):
    """
    Check that all elements from base are preserved or deleted identically in both branches.
    Returns a list of inconsistency descriptions.
    """
    issues = []

    # Check tiers
    # A tier from the base EAF should be present in both branches or not at all. When present, it should be
    # identical in both branches though allowed to differ from the base.
    for tier_id, base_tier in base.tiers.items():
        in1 = tier_id in ours.tiers
        in2 = tier_id in theirs.tiers
        if in1 and in2:
            t1 = ours.tiers[tier_id]
            t2 = theirs.tiers[tier_id]
            modified1 = not _tiers_equal(base_tier, t1)
            modified2 = not _tiers_equal(base_tier, t2)
            modified_equal = _tiers_equal(t1, t2)
            if (modified1 or modified2) and not modified_equal:
                issues.append(f"Tier '{tier_id}' differs between branches")
        elif in1 != in2:
            issues.append(f"Tier '{tier_id}' presence mismatch: ours={in1}, theirs={in2}")

    # Check annotations
    # Slightly different from tiers: we will allow changes as long as they are made in one branch only. This is a very
    # common situation, for example, when annotations are filled in on one branch only.
    for tier_id, base_tier in base.tiers.items():
        for ann_id, base_ann in base_tier.annotations.items():
            in1 = tier_id in ours.tiers and ann_id in ours.tiers[tier_id].annotations
            in2 = tier_id in theirs.tiers and ann_id in theirs.tiers[tier_id].annotations
            if in1 and in2:
                a1 = ours.tiers[tier_id].annotations[ann_id]
                a2 = theirs.tiers[tier_id].annotations[ann_id]
                modified1 = not _annotations_equal(base_ann, a1)
                modified2 = not _annotations_equal(base_ann, a2)
                modified_equal = _annotations_equal(a1, a2)
                if modified1 and modified2 and not modified_equal:
                    issues.append(f"Annotation '{ann_id}' differs between branches")
            elif in1 != in2:
                issues.append(f"Annotation '{ann_id}' presence mismatch in tier '{tier_id}': ours={in1}, theirs={in2}")

    return issues


def _collect_external_reference_divergences(base: EafTree, ours: EafTree, theirs: EafTree):
    """Check ExternalReference consistency with base."""
    issues = []
    for er_id, base_er in base.external_references.items():
        in_ours = er_id in ours.external_references
        in_theirs = er_id in theirs.external_references
        if in_ours and in_theirs:
            ours_er = ours.external_references[er_id]
            theirs_er = theirs.external_references[er_id]
            modified_ours = not _external_references_equal(base_er, ours_er)
            modified_theirs = not _external_references_equal(base_er, theirs_er)
            modified_equal = _external_references_equal(ours_er, theirs_er)
            if (modified_ours or modified_theirs) and not modified_equal:
                issues.append(f"External Reference '{er_id}' differs between branches")
        elif in_ours != in_theirs:
            issues.append(f"External Reference '{er_id}' presence mismatch: ours={in_ours}, theirs={in_theirs}")
    return issues


def _collect_cv_divergences(base: EafTree, ours: EafTree, theirs: EafTree):
    """Check ControlledVocabulary consistency with base."""
    issues = []
    for cv_id, base_cv in base.controlled_vocabularies.items():
        in_ours = cv_id in ours.controlled_vocabularies
        in_theirs = cv_id in theirs.controlled_vocabularies
        if in_ours and in_theirs:
            ours_cv = ours.controlled_vocabularies[cv_id]
            theirs_cv = theirs.controlled_vocabularies[cv_id]
            modified_ours = not _controlled_vocabularies_equal(base_cv, ours_cv)
            modified_theirs = not _controlled_vocabularies_equal(base_cv, theirs_cv)
            modified_equal = _controlled_vocabularies_equal(ours_cv, theirs_cv)
            if (modified_ours or modified_theirs) and not modified_equal:
                issues.append(f"Controlled Vocabulary '{cv_id}' differs between branches")
        elif in_ours != in_theirs:
            issues.append(f"Controlled Vocabulary '{cv_id}' presence mismatch: ours={in_ours}, theirs={in_theirs}")
    return issues


def _collect_lt_divergences(base: EafTree, ours: EafTree, theirs: EafTree):
    """Check LinguisticType consistency with base."""
    issues = []
    for lt_id, base_lt in base.linguistic_types.items():
        in_ours = lt_id in ours.linguistic_types
        in_theirs = lt_id in theirs.linguistic_types
        if in_ours and in_theirs:
            ours_lt = ours.linguistic_types[lt_id]
            theirs_lt = theirs.linguistic_types[lt_id]
            modified_ours = not _linguistic_types_equal(base_lt, ours_lt)
            modified_theirs = not _linguistic_types_equal(base_lt, theirs_lt)
            modified_equal = _linguistic_types_equal(ours_lt, theirs_lt)
            if (modified_ours or modified_theirs) and not modified_equal:
                issues.append(f"Linguistic Type '{lt_id}' differs between branches")
        elif in_ours != in_theirs:
            issues.append(f"Linguistic Type '{lt_id}' presence mismatch: ours={in_ours}, theirs={in_theirs}")
    return issues


def _compare_tiers(tree1: EafTree, tree2: EafTree):
    """
    Compare tiers that exist in both EAF trees.
    Returns a list of inconsistency descriptions for shared tiers with different properties.
    """
    issues = []
    shared_tier_ids = set(tree1.tiers.keys()) & set(tree2.tiers.keys())

    for tier_id in shared_tier_ids:
        t1 = tree1.tiers[tier_id]
        t2 = tree2.tiers[tier_id]
        if not _tiers_equal(t1, t2):
            issues.append(f"Shared tier '{tier_id}' has different properties between tree1 and tree2.")
    return issues


def _get_sorted_alignable_annotations(tree):
    return sorted([ann for ann in tree.annotations.values()
                   if ann.annotation_type == Annotation.ALIGNABLE_ANNOTATION
                       and ann.tier.participant is not None],
                  key=lambda x: (x.onset, x.offset))


def _collect_overlapping_annotations(tree_a, tree_b, label_a, label_b):
    overlaps = []

    tree_a_annotations = _get_sorted_alignable_annotations(tree_a)
    tree_b_annotations = _get_sorted_alignable_annotations(tree_b)
    i, j = 0, 0

    while i < len(tree_a_annotations) and j < len(tree_b_annotations):
        annotation_a = tree_a_annotations[i]
        annotation_b = tree_b_annotations[j]

        if annotation_a.id == annotation_b.id:
            i += 1
            j += 1
            continue

        onset_a, offset_a = annotation_a.onset, annotation_a.offset
        onset_b, offset_b = annotation_b.onset, annotation_b.offset
        if onset_a < offset_b and onset_b < offset_a:
            msg = f"Overlapping annotations: {label_a} '{annotation_a.id}' and {label_b} '{annotation_b.id}'"
            overlaps.append(msg)

        if onset_a <= onset_b:
            if offset_a <= offset_b:
                i += 1
            else:
                j += 1
        else:  # onset_a > onset_b
            if offset_b <= offset_a:
                j += 1
            else:
                i += 1

    return overlaps


def _disambiguate_added_ids(theirs: EafTree, ours: EafTree, base: EafTree):
    """
    All IDs in theirs that are also in ours but not in the base, will have new ids starting from the number after the
    last id used in ours. No gap filling is done.
    """
    added_ids = set(theirs.annotations.keys()) - set(base.annotations.keys())

    highest_id_num = ours.last_used_annotation_id
    id_map = {}
    new_id_counter = highest_id_num + 1

    for old_id in theirs.annotations:
        if old_id not in added_ids:
            # Original ID from base - keep it
            id_map[old_id] = old_id
        elif old_id in ours.annotations:
            # Added ID that conflicts with ours - assign new ID
            new_id = f"a{new_id_counter}"
            id_map[old_id] = new_id
            new_id_counter += 1
        else:
            # Added ID with no conflict - can keep it
            id_map[old_id] = old_id

    # Update all annotation IDs and references
    new_annotations_dict = {}
    tier_annotations_dict = {}

    for annotation in list(theirs.annotations.values()):
        old_id = annotation.id
        new_id = id_map[old_id]

        # Update the ID attribute in the XML
        annotation.inner_element.attrib[Annotation.ID] = new_id

        # Store in new dictionaries
        new_annotations_dict[new_id] = annotation

        # Prepare tier annotations updates
        tier = annotation.tier
        if tier.id not in tier_annotations_dict:
            tier_annotations_dict[tier.id] = {}
        tier_annotations_dict[tier.id][new_id] = annotation

    # Replace the original dictionaries
    theirs.annotations.clear()
    theirs.annotations.update(new_annotations_dict)

    # Update tier annotations
    for tier_id, annotations in tier_annotations_dict.items():
        tier = theirs.tiers[tier_id]
        tier.annotations.clear()
        tier.annotations.update(annotations)

    for annotation in theirs.annotations.values():
        if annotation.annotation_type == Annotation.REF_ANNOTATION:
            old_ref = annotation.annotation_ref
            if old_ref in id_map and id_map[old_ref] != old_ref:
                annotation.inner_element.attrib[Annotation.ANNOTATION_REF] = id_map[old_ref]

    # Note: last_used_annotation_id is a calculated property, so the next line does actually update the value
    theirs.last_used_annotation_id = theirs.last_used_annotation_id

    return theirs


def merge_trees(base: EafTree, ours: EafTree, theirs: EafTree):
    """
    Three-way merge of EafTree objects.
    Returns (merged_tree, None) or (None, problems list).
    """
    problems = []

    # Phase 1: Check that the trees can be merged.
    # 1.1: Base consistency (Tiers and Annotations)
    problems.extend(_collect_base_divergences(base=base, ours=ours, theirs=theirs))
    # 1.2: Base consistency (External References)
    problems.extend(_collect_external_reference_divergences(base=base, ours=ours, theirs=theirs))
    # 1.3: Base consistency (Controlled Vocabularies)
    problems.extend(_collect_cv_divergences(base=base, ours=ours, theirs=theirs))
    # 1.4: Base consistency (Linguistic Types)
    problems.extend(_collect_lt_divergences(base=base, ours=ours, theirs=theirs))

    # 1.5: Tier consistency (Shared tiers between ours and theirs)
    problems.extend(_compare_tiers(ours, theirs))

    # 1.6: Annotations don't overlap
    # Check that new annotations in tree1 and tree2 do not overlap with each other or base
    problems.extend(_collect_overlapping_annotations(theirs, base, "theirs", "base"))
    problems.extend(_collect_overlapping_annotations(ours, base, "ours", "base"))
    problems.extend(_collect_overlapping_annotations(theirs, ours, "theirs", "ours"))

    if problems:
        return None, problems

    # Phase 2: merge
    # 2.1: Update annotations IDs in theirs to avoid conflicts with ours.
    theirs_copy = _disambiguate_added_ids(theirs=copy.deepcopy(theirs), ours=ours, base=base)

    # Start with our version as the base for merging
    merged = copy.deepcopy(ours)

    # 2.2: For each modified base annotation, use the modified version.
    for ann_id, base_ann in base.annotations.items():
        in_ours = ann_id in ours.annotations
        in_theirs = ann_id in theirs_copy.annotations

        # Skip annotations that were deleted in both branches
        if not in_ours and not in_theirs:
            continue

        # This should have been caught by _collect_base_divergences, but it doesn't hurt to check again
        if in_ours != in_theirs:
            raise ValueError(f"Annotation '{ann_id}' is present in one branch but not the other.")

        # Get annotations from both branches if they exist
        our_ann = ours.annotations[ann_id]
        their_ann = theirs_copy.annotations[ann_id]
        our_modified = not _annotations_equal(base_ann, our_ann)
        their_modified = not _annotations_equal(base_ann, their_ann)

        # Their branch modified it, ours didn't - use their version
        if their_modified and not our_modified:
            merged_ann = merged.annotations[ann_id]

            # Update value
            merged_ann.value_element.text = their_ann.value

            # Update type-specific properties
            if their_ann.annotation_type == Annotation.ALIGNABLE_ANNOTATION:
                merged_ann.inner_element.attrib[Annotation.TIME_SLOT_REF1] = their_ann.time_slot_ref1
                merged_ann.inner_element.attrib[Annotation.TIME_SLOT_REF2] = their_ann.time_slot_ref2
            elif their_ann.annotation_type == Annotation.REF_ANNOTATION:
                merged_ann.inner_element.attrib[Annotation.ANNOTATION_REF] = their_ann.annotation_ref

            # For controlled vocabulary annotations, update CVE_REF if present
            if (their_ann.tier.uses_cv and
                    Annotation.CVE_REF in their_ann.inner_element.attrib):
                merged_ann.inner_element.attrib[Annotation.CVE_REF] = \
                    their_ann.inner_element.attrib[Annotation.CVE_REF]

    # 2.3: Add tiers only present in theirs

    # 2.3.1: Independent tiers
    for tier_id, their_tier in theirs_copy.tiers.items():
        if tier_id not in merged.tiers and their_tier.parent_ref is None:
            # Create the new independent tier in merged
            merged.add_tier(
                tier_id=tier_id,
                linguistic_type=their_tier.linguistic_type_ref,
                participant=their_tier.participant
            )

    # 2.3.2: Dependent tiers

    # 2.3.2.1: Add as many as we can
    # We need to add parent tiers before we add their dependents. We will ensure this order by only adding a dependent
    # tier if its parent is already present in merged and looping until no more dependent tiers can be added.
    added_tier = True
    while added_tier:
        added_tier = False
        for tier_id, their_tier in theirs_copy.tiers.items():
            if (tier_id not in merged.tiers and their_tier.parent_ref is not None
                    and their_tier.parent_ref in merged.tiers):
                # Create the new dependent tier in merged
                merged.add_tier(
                    tier_id=tier_id,
                    linguistic_type=their_tier.linguistic_type_ref,
                    parent_tier=merged.tiers[their_tier.parent_ref]
                )
                added_tier = True

    # 2.3.2.2: Check for tiers that we weren't able to add
    for tier_id, their_tier in theirs_copy.tiers.items():
        if tier_id not in merged.tiers:
            if their_tier.parent_ref is not None and their_tier.parent_ref not in merged.tiers:
                problems.append(f"Tier '{tier_id}' could not be added because its parent tier "
                                f"'{their_tier.parent_ref}' does not exist in the merged result.")

    # 2.4: Copy new annotations from theirs (ones not in base)

    # 2.4.1. First, process all ALIGNABLE_ANNOTATIONs to ensure they exist when processing reference annotations
    for ann_id, their_ann in theirs_copy.annotations.items():
        if (ann_id not in base.annotations and
                ann_id not in merged.annotations and
                their_ann.annotation_type == Annotation.ALIGNABLE_ANNOTATION):

            tier_id = their_ann.tier.id
            if tier_id in merged.tiers:
                tier = merged.tiers[tier_id]
                tier.add_alignable_annotation(
                    onset_ms=their_ann.onset,
                    offset_ms=their_ann.offset,
                    value=their_ann.value,
                    annotation_id=ann_id
                )
            else:
                # We already logged this problem when adding tiers, so we don't need to log it again
                pass

    # 2.4.2: Process REF_ANNOTATIONs with dependency resolution
    # First, collect all reference annotations that need to be added
    ref_annotations_to_add = {
        ann_id: their_ann for ann_id, their_ann in theirs_copy.annotations.items()
        if (ann_id not in base.annotations and
            ann_id not in merged.annotations and
            their_ann.annotation_type == Annotation.REF_ANNOTATION)
    }

    # Keep trying until no more annotations can be added
    added_annotation = True
    while added_annotation and ref_annotations_to_add:
        added_annotation = False

        # Try to add annotations whose parents exist
        for ann_id, their_ann in list(ref_annotations_to_add.items()):
            tier_id = their_ann.tier.id
            if tier_id in merged.tiers and their_ann.annotation_ref in merged.annotations:
                tier = merged.tiers[tier_id]
                tier.add_reference_annotation(
                    parent_annotation_id=their_ann.annotation_ref,
                    value=their_ann.value,
                    annotation_id=ann_id
                )
                del ref_annotations_to_add[ann_id]
                added_annotation = True

    # Any remaining annotations couldn't be added due to missing parents
    for ann_id, their_ann in ref_annotations_to_add.items():
        problems.append(
            f"Cannot add reference annotation '{ann_id}' - parent '{their_ann.annotation_ref}' not found")

    if problems:
        return None, problems

    return merged, []
