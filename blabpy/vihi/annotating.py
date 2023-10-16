from ..git_utils import sparse_clone
from .paths import get_lena_recording_path, parse_full_recording_id, get_lena_annotations_path


def checkout_recording_for_annotation(full_recording_id, annotator_name):
    """
    Checks out a recording from the LENA repo into an individual folder for the annotator.
    :param full_recording_id: XX_MMM_NNN
    :param annotator_name: "First Last"
    :return: Path object to the checked-out folder.
    """
    pn_opus_repo_path = get_lena_annotations_path()
    recording_folder = get_lena_recording_path(**parse_full_recording_id(full_recording_id),
                                               assert_exists=True)

    # The folder name and the branch name contain both the recording ID and the annotator's name.
    annotation_id = f'{full_recording_id}_{annotator_name.replace(" ", "-")}'
    new_branch_name = f'annotating/{annotation_id}'

    individual_folder = pn_opus_repo_path / 'annotations-in-progress' / annotation_id
    if individual_folder.exists():
        raise Exception(f'There is already a folder with in-progress annotations at\n'
                        f'{individual_folder.as_posix()}\n'
                        f'Continue annotating in that folder.\n'
                        f'\n'
                        f'If, however, that folder is empty or doesn\'t contain the annotation files,\n'
                        f'it is possible that an error occurred while the script created that folder.\n'
                        f'In that case, delete the folder completely and re-run the command.')

    _ = sparse_clone(
        remote_uri=pn_opus_repo_path,
        folder_to_clone_into=individual_folder,
        checked_out_folder=recording_folder.relative_to(pn_opus_repo_path),
        new_branch_name=new_branch_name,
        remote_name='vihi_main',
        source_branch='main',
        mark_folder_as_safe=True,
        depth=1)

    return individual_folder
