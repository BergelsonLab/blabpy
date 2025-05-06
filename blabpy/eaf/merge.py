import copy
from .eaf_tree import EafTree, Annotation


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


def _collect_base_divergences(base: EafTree, tree1: EafTree, tree2: EafTree):
    """
    Check that all elements from base are preserved or deleted identically in both branches.
    Returns a list of inconsistency descriptions.
    """
    issues = []

    # Check tiers
    # A tier from the base EAF should be present in both branches or not at all. When present, it should be
    # identical in both branches though allowed to differ from the base.
    for tier_id, base_tier in base.tiers.items():
        in1 = tier_id in tree1.tiers
        in2 = tier_id in tree2.tiers
        if in1 and in2:
            t1 = tree1.tiers[tier_id]
            t2 = tree2.tiers[tier_id]
            modified1 = not _tiers_equal(base_tier, t1)
            modified2 = not _tiers_equal(base_tier, t2)
            modified_equal = _tiers_equal(t1, t2)
            if (modified1 or modified2) and not modified_equal:
                issues.append(f"Tier '{tier_id}' differs between branches")
        elif in1 != in2:
            issues.append(f"Tier '{tier_id}' presence mismatch: branch1={in1}, branch2={in2}")


    # Check annotations
    # Slightly different from tiers: we will allow changes as long as they are made in one branch only. This is a very
    # common situation, for example, when annotations are filled in on one branch only.
    for tier_id, base_tier in base.tiers.items():
        for ann_id, base_ann in base_tier.annotations.items():
            in1 = tier_id in tree1.tiers and ann_id in tree1.tiers[tier_id].annotations
            in2 = tier_id in tree2.tiers and ann_id in tree2.tiers[tier_id].annotations
            if in1 and in2:
                a1 = tree1.tiers[tier_id].annotations[ann_id]
                a2 = tree2.tiers[tier_id].annotations[ann_id]
                modified1 = not _annotations_equal(base_ann, a1)
                modified2 = not _annotations_equal(base_ann, a2)
                modified_equal = _annotations_equal(a1, a2)
                if modified1 and modified2 and not modified_equal:
                    issues.append(f"Annotation '{ann_id}' differs between branches")
            elif in1 != in2:
                issues.append(f"Annotation '{ann_id}' presence mismatch in tier '{tier_id}': branch1={in1}, branch2={in2}")

    return issues


def merge_trees(base: EafTree, tree1: EafTree, tree2: EafTree):
    """
    Three-way merge of EafTree objects.
    Returns (merged_tree or None, problems list).
    'problems' includes base divergences and cross-branch annotation conflicts.
    """
    problems = []

    # Phase 1: Check that the trees can be merged.

    # Step 1: Base consistency
    problems.extend(_collect_base_divergences(base, tree1, tree2))

    # Step 2: Tier consistency
    problems.extend(_compare_tiers(tree1, tree2))

    # Step 3: Annotations
    base_ann = set(base.annotations.keys())
    t1_ann = set(tree1.annotations.keys())
    t2_ann = set(tree2.annotations.keys())
    t1_added_ann = t1_ann - base_ann
    t2_added_ann = t2_ann - base_ann
    raise NotImplementedError("TODO: handle adding new annotations")

    # Step 3.1: Check for overlapping alignable annotations either on the same tier or different tiers
    # Step 3.2: Check for reference annotation values

    # Step 4: Update annotation and timestamp ids for tree2 to avoid conflicts with tree1

    if problems:
        return None, problems

    # Phase 2: merge
    # 2.1: Copy tree2 updating ids of annotations and timestamps to avoid conflicts with tree1.
    # 2.2: Copy tree1.
    # 2.3: Copy the new tiers and annotations from tree2 (with ids already updated).
    tree2 = _disambiguate_ids(copy.deepcopy(tree2), merged)
    merged = _simple_merge(copy.deepcopy(tree1), tree2)


    return merged, []
