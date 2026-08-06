import os
from datetime import datetime

from config import ROOT_DIR, get_dub_pipeline_config
from cache import get_accounts
from status import info, success, warning
from .DouyinDiscovery import DouyinDiscovery
from .DubArtifacts import DubRunContext
from .DubAsr import DubAsr
from .DubAudioProcessor import DubAudioProcessor
from .DubMetadata import DubMetadata
from .DubRunCleanup import DubRunCleanup
from .DubSubtitleRenderer import DubSubtitleRenderer
from .DubTimelineMixer import DubTimelineMixer
from .DubTopicPlanner import DubTopicPlanner
from .DubTranslator import DubTranslator
from .DubTts import DubTts
from .DubUploadAdapter import DubUploadAdapter
from .DubVideoDownloader import DubVideoDownloader
from .DubVideoRenderer import DubVideoRenderer
from .XiaohongshuDiscovery import XiaohongshuDiscovery


class DubPipeline:
    def __init__(self, account_id: str = "") -> None:
        self.config = get_dub_pipeline_config()
        self.account_id = account_id
        self._apply_account_browser_profile()

    def run(self) -> DubRunContext:
        if not self.config.get("enabled"):
            raise RuntimeError("dub_pipeline.enabled is false")

        context = self._create_run_context()
        info(f" => Dub pipeline run dir: {context.run_dir}")

        topic_selection = DubTopicPlanner(self.config).select_topic(context.run_dir)
        candidates = self._discover(topic_selection["keyword"], context.run_dir)
        source_video_path = DubVideoDownloader(self.config).download(context.run_dir, candidates)

        audio_processor = DubAudioProcessor(self.config)
        original_audio_path = audio_processor.extract_audio(source_video_path, context.run_dir)

        original_segments = DubAsr(self.config).transcribe(original_audio_path, context.run_dir)
        background_path = audio_processor.prepare_background(
            original_audio_path,
            context.run_dir,
            original_segments,
        )
        vi_segments = DubTranslator(self.config).translate(original_segments, context.run_dir)
        rendered_segments = DubTts(self.config).synthesize_segments(vi_segments, context.run_dir)

        audio_vi_path = DubTimelineMixer(self.config).mix(
            rendered_segments,
            background_path,
            context.run_dir,
        )
        dubbed_video_path = DubVideoRenderer(self.config).render(
            source_video_path,
            audio_vi_path,
            context.run_dir,
        )
        dubbed_video_path = DubSubtitleRenderer(self.config).burn(
            dubbed_video_path,
            vi_segments,
            context.run_dir,
        )

        metadata = DubMetadata(self.config).generate(
            topic_selection,
            vi_segments,
            context.run_dir,
        )
        upload_result = DubUploadAdapter(self.config, self.account_id).upload(
            dubbed_video_path,
            os.path.join(context.run_dir, "youtube_metadata.json"),
            os.path.join(context.run_dir, "caption.txt"),
            context.run_dir,
        )
        DubRunCleanup(self.config).cleanup_after_successful_upload(
            context.run_dir,
            upload_result,
        )

        success("PIPELINE COMPLETE")
        return context

    def _create_run_context(self) -> DubRunContext:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        language = self.config.get("language", "vi")
        country = self.config.get("country", "VN")
        run_id = f"{timestamp}_{language}"
        output_root = self.config.get("output_root", "output/dub_pipeline")
        if not os.path.isabs(output_root):
            output_root = os.path.join(ROOT_DIR, output_root)
        run_dir = os.path.join(output_root, country, run_id)
        os.makedirs(run_dir, exist_ok=False)
        return DubRunContext(run_dir=run_dir, run_id=run_id, config=self.config)

    def _discover(self, keyword: str, run_dir: str) -> list[dict]:
        source_video_path = self.config.get("source_video_path", "")
        if source_video_path:
            return [
                {
                    "source": "local_file",
                    "keyword": keyword,
                    "url": source_video_path,
                    "selected": True,
                }
            ]

        errors = []
        all_candidates = []
        for source in self.config.get("sources", []):
            try:
                if source == "xiaohongshu":
                    candidates = XiaohongshuDiscovery(self.config).discover(keyword, run_dir)
                elif source == "douyin":
                    candidates = DouyinDiscovery(self.config).discover(keyword, run_dir)
                else:
                    warning(f"Unsupported dub discovery source: {source}")
                    continue

                if candidates:
                    all_candidates.extend(candidates)
                else:
                    warning(f"No candidates from {source}; trying next source.")
            except NotImplementedError as exc:
                errors.append(str(exc))
            except Exception as exc:
                errors.append(f"{source}: {exc}")

        if all_candidates:
            return all_candidates

        error_message = "No discovery source returned candidates. " + " ".join(errors)
        DubVideoDownloader(self.config)._write_outputs(
            run_dir,
            [],
            {
                "source": "discovery",
                "error": error_message,
            },
        )
        raise RuntimeError(error_message)

    def _apply_account_browser_profile(self) -> None:
        if self.config.get("browser_profile"):
            return

        accounts = get_accounts("youtube")
        selected_account = None

        if self.account_id:
            for account in accounts:
                if account.get("id") == self.account_id:
                    selected_account = account
                    break
        elif accounts:
            selected_account = accounts[0]

        if not selected_account:
            return

        firefox_profile = str(selected_account.get("firefox_profile", "")).strip()
        if not firefox_profile:
            return

        self.config["browser_profile"] = firefox_profile
        info(f" => Using YouTube account Firefox profile for discovery: {firefox_profile}")
