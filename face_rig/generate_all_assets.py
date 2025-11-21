#!/usr/bin/env python3
"""
generate_all_assets.py

Master script to orchestrate the complete asset generation pipeline.
Runs all generation scripts in sequence to create a full character rig.

Pipeline stages:
1. generate_extreme_expressions.py - Generate endpoint expression images
2. generate_head_tilts.py - Generate head pose variants for each expression
3. generate_all_sequences.py - Generate expression-to-expression transition sequences
4. generate_neutral_pose_sequences.py - Generate pose-to-pose transitions for neutral

Usage:
    export OPENAI_API_KEY=sk-...
    
    python generate_all_assets.py \\
        --config expressions.json \\
        --base-image watercolor_boy_greenscreen.png \\
        --max-workers 4 \\
        --overwrite
    
Options:
    --skip-extremes     Skip stage 1 (expression endpoints)
    --skip-tilts        Skip stage 2 (head poses)
    --skip-sequences    Skip stage 3 (expression transitions)
    --skip-neutral-pose Skip stage 4 (pose transitions)
    --dry-run           Print commands without executing
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Optional


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_stage(stage_num: int, stage_name: str):
    """Print a stage header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}")
    print(f"STAGE {stage_num}: {stage_name}")
    print(f"{'='*80}{Colors.RESET}\n")


def run_command(cmd: List[str], description: str, dry_run: bool = False) -> bool:
    """
    Run a command and return success status.
    
    Args:
        cmd: Command and arguments as list
        description: Human-readable description
        dry_run: If True, print command without executing
    
    Returns:
        True if successful, False otherwise
    """
    cmd_str = ' '.join(cmd)
    
    if dry_run:
        print(f"{Colors.CYAN}[DRY RUN]{Colors.RESET} {description}")
        print(f"  Command: {cmd_str}\n")
        return True
    
    print(f"{Colors.BLUE}▶{Colors.RESET} {description}")
    print(f"  {Colors.CYAN}{cmd_str}{Colors.RESET}\n")
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Print output
        if result.stdout:
            for line in result.stdout.splitlines():
                print(f"  {line}")
        
        print(f"{Colors.GREEN}✓{Colors.RESET} {description} completed\n")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}✗{Colors.RESET} {description} failed!")
        print(f"{Colors.RED}Error output:{Colors.RESET}")
        if e.stdout:
            for line in e.stdout.splitlines():
                print(f"  {line}")
        print()
        return False
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠{Colors.RESET} Interrupted by user\n")
        raise


def check_prerequisites(base_image: Path, config: Path) -> bool:
    """Check if required files exist"""
    print(f"{Colors.BOLD}Checking prerequisites...{Colors.RESET}")
    
    missing = []
    
    if not base_image.exists():
        missing.append(f"Base image: {base_image}")
    else:
        print(f"{Colors.GREEN}✓{Colors.RESET} Base image found: {base_image}")
    
    if not config.exists():
        missing.append(f"Config file: {config}")
    else:
        print(f"{Colors.GREEN}✓{Colors.RESET} Config found: {config}")
    
    # Check for OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY environment variable")
    else:
        print(f"{Colors.GREEN}✓{Colors.RESET} OPENAI_API_KEY is set")
    
    if missing:
        print(f"\n{Colors.RED}✗ Missing prerequisites:{Colors.RESET}")
        for item in missing:
            print(f"  - {item}")
        return False
    
    print()
    return True


def stage_1_extremes(
    config: Path,
    base_image: Path,
    endpoints_dir: Path,
    size: str,
    max_workers: int,
    overwrite: bool,
    dry_run: bool
) -> bool:
    """Stage 1: Generate extreme expression endpoints"""
    print_stage(1, "Generate Extreme Expression Endpoints")
    
    # Generate for all 5 poses
    poses = ["center", "tilt_left_small", "tilt_right_small", "nod_up_small", "nod_down_small"]
    
    for pose in poses:
        cmd = [
            sys.executable,
            "generate_extreme_expressions.py",
            "--config", str(config),
            "--base-image", str(base_image),
            "--pose", pose,
            "--outdir", str(endpoints_dir),
            "--size", size,
            "--max-workers", str(max_workers),
            "--include-neutral"
        ]
        
        if overwrite:
            cmd.append("--overwrite")
        
        if not run_command(
            cmd,
            f"Generating extreme expressions for pose: {pose}",
            dry_run
        ):
            return False
    
    return True


def stage_2_tilts(
    config: Path,
    endpoints_dir: Path,
    size: str,
    max_workers: int,
    overwrite: bool,
    dry_run: bool
) -> bool:
    """Stage 2: Generate head pose tilts for each expression"""
    print_stage(2, "Generate Head Pose Variants")
    
    cmd = [
        sys.executable,
        "generate_head_tilts.py",
        "--config", str(config),
        "--endpoints-dir", str(endpoints_dir),
        "--base-neutral", str(endpoints_dir / "neutral__center.png"),
        "--source-pose", "center",
        "--size", size,
        "--max-workers", str(max_workers)
    ]
    
    if overwrite:
        cmd.append("--overwrite")
    
    return run_command(
        cmd,
        "Generating head pose variants for all expressions",
        dry_run
    )


def stage_3_sequences(
    config: Path,
    endpoints_dir: Path,
    sequences_dir: Path,
    size: str,
    max_workers: int,
    max_depth: int,
    overwrite: bool,
    dry_run: bool
) -> bool:
    """Stage 3: Generate expression-to-expression transition sequences"""
    print_stage(3, "Generate Expression Transition Sequences")
    
    cmd = [
        sys.executable,
        "generate_all_sequences.py",
        "--config", str(config),
        "--endpoints-dir", str(endpoints_dir),
        "--sequences-dir", str(sequences_dir),
        "--max-depth", str(max_depth),
        "--size", size,
        "--max-workers", str(max_workers)
    ]
    
    if overwrite:
        cmd.append("--overwrite")
    
    return run_command(
        cmd,
        "Generating expression-to-expression transitions",
        dry_run
    )


def stage_4_neutral_pose(
    config: Path,
    endpoints_dir: Path,
    sequences_dir: Path,
    size: str,
    max_workers: int,
    max_depth: int,
    overwrite: bool,
    dry_run: bool
) -> bool:
    """Stage 4: Generate neutral pose-to-pose transitions"""
    print_stage(4, "Generate Neutral Pose Transitions")
    
    cmd = [
        sys.executable,
        "generate_neutral_pose_sequences.py",
        "--config", str(config),
        "--endpoints-dir", str(endpoints_dir),
        "--sequences-dir", str(sequences_dir),
        "--source-pose", "center",
        "--size", size,
        "--max-workers", str(max_workers),
        "--max-depth", str(max_depth)
    ]
    
    if overwrite:
        cmd.append("--overwrite")
    
    return run_command(
        cmd,
        "Generating neutral pose-to-pose transitions",
        dry_run
    )


def main():
    parser = argparse.ArgumentParser(
        description="Master script to generate complete character rig assets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate everything from scratch
    python generate_all_assets.py \\
        --config expressions.json \\
        --base-image watercolor_boy_greenscreen.png \\
        --max-workers 4

    # Regenerate only sequences (skip endpoints and poses)
    python generate_all_assets.py \\
        --config expressions.json \\
        --base-image watercolor_boy_greenscreen.png \\
        --skip-extremes \\
        --skip-tilts \\
        --overwrite

    # Dry run to see what would be executed
    python generate_all_assets.py \\
        --config expressions.json \\
        --base-image watercolor_boy_greenscreen.png \\
        --dry-run
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--config",
        type=Path,
        default="expressions.json",
        help="Path to expressions.json (default: expressions.json)"
    )
    parser.add_argument(
        "--base-image",
        type=Path,
        required=True,
        help="Path to neutral base PNG (e.g., watercolor_boy_greenscreen.png)"
    )
    
    # Directory arguments
    parser.add_argument(
        "--endpoints-dir",
        type=Path,
        default="frames/endpoints",
        help="Output directory for endpoint expressions (default: frames/endpoints)"
    )
    parser.add_argument(
        "--sequences-dir",
        type=Path,
        default="frames/sequences",
        help="Output directory for transition sequences (default: frames/sequences)"
    )
    
    # Generation parameters
    parser.add_argument(
        "--size",
        default="1024x1536",
        help="Image size (default: 1024x1536)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Max intermediate frames for sequences (default: 3)"
    )
    
    # Control flags
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing"
    )
    
    # Stage skip flags
    parser.add_argument(
        "--skip-extremes",
        action="store_true",
        help="Skip stage 1 (extreme expression endpoints)"
    )
    parser.add_argument(
        "--skip-tilts",
        action="store_true",
        help="Skip stage 2 (head pose tilts)"
    )
    parser.add_argument(
        "--skip-sequences",
        action="store_true",
        help="Skip stage 3 (expression transitions)"
    )
    parser.add_argument(
        "--skip-neutral-pose",
        action="store_true",
        help="Skip stage 4 (neutral pose transitions)"
    )
    
    args = parser.parse_args()
    
    # Print header
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}")
    print("CHARACTER RIG ASSET GENERATION PIPELINE")
    print(f"{'='*80}{Colors.RESET}\n")
    
    # Check prerequisites
    if not check_prerequisites(args.base_image, args.config):
        print(f"\n{Colors.RED}Aborting due to missing prerequisites.{Colors.RESET}\n")
        return 1
    
    # Create output directories
    if not args.dry_run:
        args.endpoints_dir.mkdir(parents=True, exist_ok=True)
        args.sequences_dir.mkdir(parents=True, exist_ok=True)
        print(f"{Colors.GREEN}✓{Colors.RESET} Created output directories\n")
    
    # Track overall success
    all_success = True
    stages_run = 0
    stages_total = 4
    
    # Stage 1: Extreme expressions
    if not args.skip_extremes:
        stages_run += 1
        if not stage_1_extremes(
            args.config,
            args.base_image,
            args.endpoints_dir,
            args.size,
            args.max_workers,
            args.overwrite,
            args.dry_run
        ):
            all_success = False
            print(f"{Colors.RED}Stage 1 failed. Aborting pipeline.{Colors.RESET}\n")
            return 1
    else:
        print(f"{Colors.YELLOW}⊘ Skipping Stage 1 (extreme expressions){Colors.RESET}\n")
    
    # Stage 2: Head tilts
    if not args.skip_tilts:
        stages_run += 1
        if not stage_2_tilts(
            args.config,
            args.endpoints_dir,
            args.size,
            args.max_workers,
            args.overwrite,
            args.dry_run
        ):
            all_success = False
            print(f"{Colors.RED}Stage 2 failed. Aborting pipeline.{Colors.RESET}\n")
            return 1
    else:
        print(f"{Colors.YELLOW}⊘ Skipping Stage 2 (head tilts){Colors.RESET}\n")
    
    # Stage 3: Expression sequences
    if not args.skip_sequences:
        stages_run += 1
        if not stage_3_sequences(
            args.config,
            args.endpoints_dir,
            args.sequences_dir,
            args.size,
            args.max_workers,
            args.max_depth,
            args.overwrite,
            args.dry_run
        ):
            all_success = False
            print(f"{Colors.RED}Stage 3 failed. Aborting pipeline.{Colors.RESET}\n")
            return 1
    else:
        print(f"{Colors.YELLOW}⊘ Skipping Stage 3 (expression sequences){Colors.RESET}\n")
    
    # Stage 4: Neutral pose sequences
    if not args.skip_neutral_pose:
        stages_run += 1
        if not stage_4_neutral_pose(
            args.config,
            args.endpoints_dir,
            args.sequences_dir,
            args.size,
            args.max_workers,
            args.max_depth,
            args.overwrite,
            args.dry_run
        ):
            all_success = False
            print(f"{Colors.RED}Stage 4 failed. Aborting pipeline.{Colors.RESET}\n")
            return 1
    else:
        print(f"{Colors.YELLOW}⊘ Skipping Stage 4 (neutral pose sequences){Colors.RESET}\n")
    
    # Final summary
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}")
    print("PIPELINE COMPLETE")
    print(f"{'='*80}{Colors.RESET}\n")
    
    if all_success:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ All stages completed successfully!{Colors.RESET}")
        print(f"  Stages run: {stages_run}/{stages_total}")
        print(f"  Endpoints: {args.endpoints_dir}")
        print(f"  Sequences: {args.sequences_dir}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Pipeline failed with errors{Colors.RESET}")
        return 1
    
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Pipeline interrupted by user.{Colors.RESET}\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

