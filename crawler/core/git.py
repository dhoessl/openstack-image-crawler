import git
import os
from loguru import logger
from pathlib import Path

from crawler.core.database import Database


def clone_or_pull(
    remote_repository: str, repository: str,
    working_branch: str, ssh_command: str
) -> None:
    if ssh_command:
        os.environ["GIT_SSH_COMMAND"] = ssh_command
    path = Path(repository)
    if not path.is_dir():
        logger.info(
            "Cloning repository {remote_repository} ({working_branch}) "
            "into {repository}"
        )
        try:
            image_repo = git.Repo.clone_from(
                remote_repository, repository, branch=working_branch
            )
        except git.exc.GitCommandError as error:
            raise RuntimeError(
                f"Cloning of {remote_repository} failed with {error}"
            )
    else:
        logger.info(
            f"Repository exists already, pulling changes ({working_branch})"
        )
        image_repo = git.Repo(repository)
        try:
            image_repo.remotes.origin.pull()
        except git.exc.GitCommandError as error:
            raise RuntimeError(f"Update (pull) failed with {error}")

        try:
            image_repo.git.checkout(working_branch)
        except git.exc.GitCommandError as error:
            raise RuntimeError(
                f"Checkout on branch {working_branch} failed with {error}"
            )


def update_repository(
    database: Database, repository: str,
    updated_sources: dict, ssh_command: str
) -> None:
    if ssh_command:
        os.environ["GIT_SSH_COMMAND"] = ssh_command
    image_repo = git.Repo(repository)
    if image_repo.is_dirty(untracked_files=True):
        logger.info("Changes in local repository detected.")

        all_changes = []

        untracked_files = image_repo.untracked_files
        if untracked_files:
            logger.info("New untracked files:{'\n'.join(untracked_files)}")
            for file in untracked_files:
                all_changes.append(file)

        changed_files = image_repo.git.diff(None, name_only=True)
        if changed_files:
            logger.info(f"Updated files:\n{changed_files}")
            for file in changed_files.split("\n"):
                all_changes.append(file)

        releases_list = []
        for source in updated_sources:
            for release in updated_sources[source]["releases"]:
                logger.debug(f"get release version data for {source} {release}")
                release_data = database.get_release_version(
                    source, release, 1
                )
                if not release_data:
                    logger.warn("got no release version data")
                    continue
                releases_list.append(
                    f"{release_data['name']} {release_data['version']}"
                )

        commit_message = f"Add releases: {', '.join(releases_list)}"
        logger.info(f"Commit message:\n{commit_message}")

        image_repo.git.add(all_changes)
        image_repo.index.commit(commit_message)
    try:
        image_repo.remotes.origin.push()
    except Exception as error:
        raise RuntimeError(
            f"Push into upstream repository failed!\n{error}"
        )
