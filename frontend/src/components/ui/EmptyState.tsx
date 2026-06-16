import { Empty, Space, Typography } from 'antd'
import { colors, spacing, typography } from '@/styles/theme'

const { Text } = Typography

interface EmptyStateProps {
  description?: string
  subDescription?: string
}

const EmptyState: React.FC<EmptyStateProps> = ({
  description = '暂无数据',
  subDescription,
}) => {
  return (
    <div style={{ padding: spacing.xxl, textAlign: 'center' }}>
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <Space direction="vertical" size={spacing.xs}>
            <Text style={{ color: colors.textSecondary, fontSize: typography.sizes.md }}>
              {description}
            </Text>
            {subDescription && (
              <Text style={{ color: colors.textMuted, fontSize: typography.sizes.sm }}>
                {subDescription}
              </Text>
            )}
          </Space>
        }
      />
    </div>
  )
}

export default EmptyState
