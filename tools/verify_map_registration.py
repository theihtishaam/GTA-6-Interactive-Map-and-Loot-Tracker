import cv2
import numpy as np

HEIGHT = 1500
sift = cv2.SIFT_create(nfeatures=6000)


def features(path):
    source = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    scale = HEIGHT / source.shape[0]
    image = cv2.resize(source, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    keypoints, descriptors = sift.detectAndCompute(image, None)
    return keypoints, descriptors, scale


source_kp, source_des, source_scale = features('.atlas/day-map.webp')
for path in ('.atlas/powerpyx-map-original.png', '.atlas/rockstar-map-original.jpg'):
    target_kp, target_des, target_scale = features(path)
    best = cv2.BFMatcher().knnMatch(source_des, target_des, k=2)
    matches = [first for first, second in best if first.distance < .73 * second.distance]
    source = np.float32([source_kp[match.queryIdx].pt for match in matches])
    target = np.float32([target_kp[match.trainIdx].pt for match in matches])
    # Reserved controls are distributed across the image rather than one area.
    indices = np.random.default_rng(20261121).permutation(len(matches))
    train, test = indices[:len(indices) * 3 // 4], indices[len(indices) * 3 // 4:]
    matrix, mask = cv2.estimateAffine2D(source[train], target[train], method=cv2.RANSAC,
                                        ransacReprojThreshold=2, refineIters=20)
    errors = np.linalg.norm(source[test] @ matrix[:, :2].T + matrix[:, 2] - target[test], axis=1)
    # Descriptor matching can return incorrect pairs, so report their count separately.
    accepted = errors <= 2
    native = errors[accepted] / target_scale
    print(path, len(matches), 'training', int(mask.sum()), '/', len(train),
          'holdout', int(accepted.sum()), '/', len(test))
    print('bounds', (source[test][accepted].min(axis=0)/source_scale).tolist(),
          (source[test][accepted].max(axis=0)/source_scale).tolist())
    print('matrix', np.c_[matrix[:, :2]*source_scale/target_scale, matrix[:, 2]/target_scale].tolist())
    print('median/p90/max', np.quantile(native,[.5,.9,1]).tolist())
