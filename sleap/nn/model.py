import tensorflow as tf

import attr
from typing import List, TypeVar, Optional, Text, Tuple

import sleap
from sleap.nn.architectures import (
    LeapCNN,
    UNet,
    Hourglass,
    ResNetv1,
    ResNet50,
    ResNet101,
    ResNet152,
    IntermediateFeature,
)
from sleap.nn.heads import (
    CentroidConfmapsHead,
    SingleInstanceConfmapsHead,
    CenteredInstanceConfmapsHead,
    MultiInstanceConfmapsHead,
    PartAffinityFieldsHead,
)
from sleap.nn.config import (
    LEAPConfig,
    UNetConfig,
    HourglassConfig,
    ResNetConfig,
    SingleInstanceConfmapsHeadConfig,
    CentroidsHeadConfig,
    CenteredInstanceConfmapsHeadConfig,
    MultiInstanceConfig,
    BackboneConfig,
    HeadsConfig,
    ModelConfig,
)
from sleap.nn.data.utils import ensure_list


ARCHITECTURES = [LeapCNN, UNet, Hourglass, ResNetv1, ResNet50, ResNet101, ResNet152]
ARCHITECTURE_NAMES = [cls.__name__ for cls in ARCHITECTURES]
Architecture = TypeVar("Architecture", *ARCHITECTURES)

BACKBONE_CONFIG_TO_CLS = {
    LEAPConfig: LeapCNN,
    UNetConfig: UNet,
    HourglassConfig: Hourglass,
    ResNetConfig: ResNetv1,
}

HEADS = [
    CentroidConfmapsHead,
    SingleInstanceConfmapsHead,
    CenteredInstanceConfmapsHead,
    MultiInstanceConfmapsHead,
    PartAffinityFieldsHead,
]
Head = TypeVar("Head", *HEADS)


@attr.s(auto_attribs=True)
class Model:
    backbone: Architecture
    heads: List[Head] = attr.ib(converter=ensure_list)

    @classmethod
    def from_config(
        cls, config: ModelConfig, skeleton: Optional[sleap.Skeleton] = None
    ) -> "Model":
        # Figure out which backbone class to use.
        backbone_config = config.backbone.which_oneof()
        backbone_cls = BACKBONE_CONFIG_TO_CLS[type(backbone_config)]

        # Figure out which head class to use.
        head_config = config.heads.which_oneof()
        if isinstance(head_config, SingleInstanceConfmapsHeadConfig):
            part_names = head_config.part_names
            if part_names is None:
                if skeleton is None:
                    raise ValueError(
                        "Skeleton must be provided when the head configuration is "
                        "incomplete."
                    )
                part_names = skeleton.node_names
            heads = SingleInstanceConfmapsHead.from_config(
                head_config, part_names=part_names
            )

        elif isinstance(head_config, CentroidsHeadConfig):
            heads = CentroidConfmapsHead.from_config(head_config)

        elif isinstance(head_config, CenteredInstanceConfmapsHeadConfig):
            part_names = head_config.part_names
            if part_names is None:
                if skeleton is None:
                    raise ValueError(
                        "Skeleton must be provided when the head configuration is "
                        "incomplete."
                    )
                part_names = skeleton.node_names
            heads = CenteredInstanceConfmapsHead.from_config(
                head_config, part_names=part_names
            )

        elif isinstance(head_config, MultiInstanceConfig):
            part_names = head_config.multi_instance.part_names
            if part_names is None:
                if skeleton is None:
                    raise ValueError(
                        "Skeleton must be provided when the head configuration is "
                        "incomplete."
                    )
                part_names = skeleton.node_names

            edges = head_config.pafs.edges
            if edges is None:
                if skeleton is None:
                    raise ValueError(
                        "Skeleton must be provided when the head configuration is "
                        "incomplete."
                    )
                edges = skeleton.edge_names

            heads = [
                MultiInstanceConfmapsHead.from_config(
                    head_config.multi_instance, part_names=part_names
                ),
                PartAffinityFieldsHead.from_config(head_config.pafs, edges=edges),
            ]

        return cls(backbone=backbone_cls.from_config(backbone_config), heads=heads)

    @property
    def maximum_stride(self) -> int:
        return self.backbone.maximum_stride

    def make_model(self, input_shape: Tuple[int, int, int]) -> tf.keras.Model:
        """Create a trainable model from the configuration.

        Args:
            input_shape: Tuple of (height, width, channels) specifying the shape of the
                inputs before preprocessing.
            
        Returns:
            An instantiated `tf.keras.Model`.
        """
        # Create input layer.
        x_in = tf.keras.layers.Input(input_shape, name="input")

        # Create backbone.
        x_main, x_mid = self.backbone.make_backbone(x_in=x_in)

        # Make sure main and intermediate feature outputs are lists.
        if isinstance(x_main, tf.Tensor):
            x_main = [x_main]
        if isinstance(x_mid[0], IntermediateFeature):
            x_mid = [x_mid]

        # Build output layers for each head.
        x_outs = []
        for output in self.heads:
            x_head = []
            if output.output_stride == self.backbone.output_stride:
                # The main output has the same stride as the head, so build output layer
                # from that tensor.
                for i, x in enumerate(x_main):
                    x_head.append(
                        tf.keras.layers.Conv2D(
                            filters=output.channels,
                            kernel_size=1,
                            strides=1,
                            padding="same",
                            name=f"{type(output).__name__}_{i}",
                        )(x)
                    )

            else:
                # Look for an intermediate activation that has the correct stride.
                for feats in zip(*x_mid):
                    # TODO: Test for this assumption?
                    assert all([feat.stride == feats[0].stride for feat in feats])
                    if feats[0].stride == output.output_stride:
                        for i, feat in enumerate(feats):
                            x_head.append(
                                tf.keras.layers.Conv2D(
                                    filters=output.channels,
                                    kernel_size=1,
                                    strides=1,
                                    padding="same",
                                    name=f"{type(output).__name__}_{i}",
                                )(feat.tensor)
                            )
                        break

            if len(x_head) == 0:
                raise ValueError(
                    f"Could not find a feature activation for output at stride "
                    f"{output.stride}."
                )
            x_outs.append(x_head)
        # TODO: Warn/error if x_main was not connected to any heads?

        # Create model.
        keras_model = tf.keras.Model(inputs=x_in, outputs=x_outs)
        return keras_model
