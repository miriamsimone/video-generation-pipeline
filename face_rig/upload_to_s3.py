#!/usr/bin/env python3
"""
Upload generated frames to S3 bucket for production deployment.

Usage:
    python upload_to_s3.py --bucket my-bucket --region us-east-1 [--prefix frames/] [--dry-run]

Uploads:
    - frames/sequences/* (all generated animation sequences)
    - frames/endpoints/* (all expression endpoint images)
    - expressions.json (character configuration)

Prerequisites:
    - AWS credentials configured (via ~/.aws/credentials, environment vars, or IAM role)
    - boto3 installed: pip install boto3
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Error: boto3 not installed. Install with: pip install boto3")
    sys.exit(1)


def upload_file_to_s3(
    s3_client,
    file_path: Path,
    bucket: str,
    s3_key: str,
    dry_run: bool = False,
    content_type: Optional[str] = None
) -> bool:
    """Upload a single file to S3"""
    if dry_run:
        print(f"  [DRY RUN] Would upload: {file_path} -> s3://{bucket}/{s3_key}")
        return True
    
    try:
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        # Set cache control for long-term caching (images rarely change)
        extra_args['CacheControl'] = 'public, max-age=31536000'  # 1 year
        
        s3_client.upload_file(
            str(file_path),
            bucket,
            s3_key,
            ExtraArgs=extra_args
        )
        print(f"  ✓ Uploaded: {s3_key}")
        return True
    except FileNotFoundError:
        print(f"  ✗ File not found: {file_path}")
        return False
    except NoCredentialsError:
        print("  ✗ AWS credentials not found")
        return False
    except ClientError as e:
        print(f"  ✗ Failed to upload {s3_key}: {e}")
        return False


def get_content_type(file_path: Path) -> str:
    """Determine content type based on file extension"""
    suffix = file_path.suffix.lower()
    content_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.json': 'application/json',
        '.txt': 'text/plain',
    }
    return content_types.get(suffix, 'application/octet-stream')


def upload_directory(
    s3_client,
    local_dir: Path,
    bucket: str,
    s3_prefix: str,
    dry_run: bool = False
) -> tuple[int, int]:
    """
    Recursively upload a directory to S3.
    Returns (success_count, total_count)
    """
    if not local_dir.exists():
        print(f"Warning: Directory not found: {local_dir}")
        return 0, 0
    
    success_count = 0
    total_count = 0
    
    for file_path in local_dir.rglob('*'):
        if file_path.is_file():
            # Calculate relative path from local_dir
            rel_path = file_path.relative_to(local_dir)
            s3_key = f"{s3_prefix}{rel_path}".replace('\\', '/')  # Windows compatibility
            
            content_type = get_content_type(file_path)
            
            if upload_file_to_s3(s3_client, file_path, bucket, s3_key, dry_run, content_type):
                success_count += 1
            total_count += 1
    
    return success_count, total_count


def main():
    parser = argparse.ArgumentParser(
        description="Upload generated character frames to S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload to S3 bucket
  python upload_to_s3.py --bucket my-character-assets --region us-east-1

  # Upload with custom prefix
  python upload_to_s3.py --bucket my-bucket --prefix watercolor-boy/frames/

  # Dry run (see what would be uploaded without actually uploading)
  python upload_to_s3.py --bucket my-bucket --dry-run

Environment Variables:
  AWS_ACCESS_KEY_ID     - AWS access key
  AWS_SECRET_ACCESS_KEY - AWS secret key
  AWS_SESSION_TOKEN     - AWS session token (optional, for temporary credentials)
  AWS_PROFILE           - AWS profile name (alternative to access keys)
"""
    )
    
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--prefix', default='frames/', help='S3 key prefix (default: frames/)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be uploaded without uploading')
    parser.add_argument('--profile', help='AWS profile name to use')
    parser.add_argument('--frames-dir', default='frames', help='Local frames directory (default: frames)')
    parser.add_argument('--skip-sequences', action='store_true', help='Skip uploading sequences/')
    parser.add_argument('--skip-endpoints', action='store_true', help='Skip uploading endpoints/')
    parser.add_argument('--upload-config', action='store_true', help='Also upload expressions.json')
    
    args = parser.parse_args()
    
    # Initialize S3 client
    session_kwargs = {'region_name': args.region}
    if args.profile:
        session_kwargs['profile_name'] = args.profile
    
    session = boto3.Session(**session_kwargs)
    s3_client = session.client('s3')
    
    # Verify bucket exists (unless dry run)
    if not args.dry_run:
        try:
            s3_client.head_bucket(Bucket=args.bucket)
            print(f"✓ Bucket '{args.bucket}' is accessible\n")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"Error: Bucket '{args.bucket}' does not exist")
            elif error_code == '403':
                print(f"Error: Access denied to bucket '{args.bucket}'")
            else:
                print(f"Error: {e}")
            sys.exit(1)
    
    base_dir = Path(__file__).parent
    frames_dir = base_dir / args.frames_dir
    
    if not frames_dir.exists():
        print(f"Error: Frames directory not found: {frames_dir}")
        sys.exit(1)
    
    print(f"Uploading from: {frames_dir}")
    print(f"S3 destination: s3://{args.bucket}/{args.prefix}")
    if args.dry_run:
        print("MODE: DRY RUN (no actual uploads)\n")
    print()
    
    total_success = 0
    total_files = 0
    
    # Upload sequences
    if not args.skip_sequences:
        sequences_dir = frames_dir / 'sequences'
        if sequences_dir.exists():
            print(f"📁 Uploading sequences...")
            success, total = upload_directory(
                s3_client,
                sequences_dir,
                args.bucket,
                f"{args.prefix}sequences/",
                args.dry_run
            )
            total_success += success
            total_files += total
            print(f"   Sequences: {success}/{total} files uploaded\n")
        else:
            print(f"⚠️  Sequences directory not found: {sequences_dir}\n")
    
    # Upload endpoints
    if not args.skip_endpoints:
        endpoints_dir = frames_dir / 'endpoints'
        if endpoints_dir.exists():
            print(f"📁 Uploading endpoints...")
            success, total = upload_directory(
                s3_client,
                endpoints_dir,
                args.bucket,
                f"{args.prefix}endpoints/",
                args.dry_run
            )
            total_success += success
            total_files += total
            print(f"   Endpoints: {success}/{total} files uploaded\n")
        else:
            print(f"⚠️  Endpoints directory not found: {endpoints_dir}\n")
    
    # Optionally upload config
    if args.upload_config:
        config_file = base_dir / 'expressions.json'
        if config_file.exists():
            print(f"📄 Uploading configuration...")
            s3_key = f"{args.prefix}expressions.json"
            if upload_file_to_s3(s3_client, config_file, args.bucket, s3_key, args.dry_run, 'application/json'):
                total_success += 1
            total_files += 1
            print()
    
    # Summary
    print("=" * 60)
    if args.dry_run:
        print(f"DRY RUN COMPLETE: Would upload {total_files} files")
    else:
        print(f"UPLOAD COMPLETE: {total_success}/{total_files} files uploaded successfully")
        if total_success < total_files:
            print(f"⚠️  {total_files - total_success} files failed to upload")
            sys.exit(1)
    print("=" * 60)


if __name__ == '__main__':
    main()


