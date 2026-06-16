import { Card, Space, Typography } from 'antd'
import { colors, radius, shadows, spacing, typography } from '@/styles/theme'

const { Title, Text } = Typography

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  trend?: string
  trendUp?: boolean
}

const StatCard: React.FC<StatCardProps> = ({ icon, label, value, trend, trendUp }) => {
  return (
    <Card
      style={{
        borderRadius: radius.lg,
        border: `1px solid ${colors.border}`,
        boxShadow: shadows.sm,
      }}
      bodyStyle={{ padding: spacing.lg }}
    >
      <Space align="start" size={spacing.md}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: radius.md,
            background: colors.accentLight,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: colors.accent,
            fontSize: 20,
          }}
        >
          {icon}
        </div>
        <div>
          <Text style={{ color: colors.textMuted, fontSize: typography.sizes.sm }}>{label}</Text>
          <Title level={3} style={{ margin: 0, color: colors.textPrimary, fontSize: typography.sizes['2xl'] }}>
            {value}
          </Title>
          {trend && (
            <Text style={{ color: trendUp ? colors.success : colors.error, fontSize: typography.sizes.sm }}>
              {trend}
            </Text>
          )}
        </div>
      </Space>
    </Card>
  )
}

export default StatCard
